import re

from django.contrib.auth import logout
from django.db import DatabaseError
from django.shortcuts import render, redirect

# Create your views here.
from django.urls import reverse
from django.views import View
from django.http import HttpResponseBadRequest, HttpResponse, JsonResponse

from Users.models import User
from home.models import ArticleCategory
from libs.captcha.captcha import captcha
from django_redis import get_redis_connection
from utils.response_code import RETCODE
from random import randint
from libs.yuntongxun.sms import CCP
import logging

logger = logging.getLogger("django")


class RegisterView(View):
    def get(self, request):
        return render(request, 'register.html')

    def post(self, request):
        '''
        1、接收数据
        2、验证数据
            2.1 参数是否齐全
            2.2 手机号格式是否正确
            2.3 密码是否符合格式
            2.4 密码和确认密码确认一致
            2.5 验证短信验证码是否和redis一致
        3、保存注册信息
        4、返回响应跳转到指定页面
        :param request:
        :return:
        '''
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        smscode = request.POST.get('sms_code')

        if not all([mobile, password, password2, smscode]):
            return HttpResponseBadRequest('缺少必要的参数')
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('手机号不符合规则')

        if not re.match(r'^[0-9A-Za-z]{8,20}$', password):
            return HttpResponseBadRequest('请输入8-20位密码，密码是数字、字母的组合')

        if password != password2:
            return HttpResponseBadRequest('两次密码输入不一致')

        redis_conn = get_redis_connection('default')

        redis_sms_code = redis_conn.get('sms:%s' % mobile)

        if redis_sms_code is None:
            return HttpResponseBadRequest('短信验证码已过期')

        if smscode != redis_sms_code.decode():
            return HttpResponseBadRequest('短信验证码不一致')

        # create_user 可以使用系统的方法对密码进行加密
        try:
            user = User.objects.create_user(
                username=mobile,
                mobile=mobile,
                password=password
            )
            # print(mobile, password)

        except DatabaseError as e:
            logger.error(e)
            return HttpResponseBadRequest('注册失败')

        # 暂时返回一个注册成功的信息，后期再实现跳转到指定页面
        # return HttpResponse('注册成功，重定向到首页')
        # 重定向  namespace:name 获取视图对应的路由

        from django.contrib.auth import login
        # 本质上会在后端为该用户生成相关session数据
        login(request, user)  # 实现状态保持

        # reverse 可以通过namespace:name来获取到视图所对应的路由
        response = redirect(reverse('home:index'))

        # 设置cookie信息，以方便首页中用户信息展示的判断和用户信息的展示
        response.set_cookie('is_login', True)
        response.set_cookie('username', user.username, max_age=7 * 24 * 3600)

        return response


class ImageCodeView(View):

    def get(self, request):
        """
        1、接收前端传递过的uuid
        2、判断uuid是否获取到
        3、通过调用captcha，生成图片验证码（图片二进制和图片内容）
        4、将图片内容保存到redis中
            uuid作为key，图片内容作为value，同时设置一个时效
        5、返回图片二进制
        :param request:
        :return:
        """
        uuid = request.GET.get('uuid')
        if uuid is None:
            return HttpResponseBadRequest('没有传递uuid')

        text, image = captcha.generate_captcha()
        redis_conn = get_redis_connection('default')
        # 设置key、过期时间和值
        redis_conn.setex(name="img:%s" % uuid, time=300, value=text)

        return HttpResponse(image, content_type='image/jpeg')


class SmsCodeView(View):
    def get(self, request):
        '''
        1、接收参数
        2、验证参数
            2.1 验证参数是否齐全
            2.2 图片验证码的验证
                2.2.1 链接redis，获取redis中的图片验证码，
                      判断图片验证码是否存在
                      如果验证码未过期，则获取之后删除验证码
                      比对图片验证码（注意大小写问题的处理）
        3、生成短信验证码
        4、保存短信验证码至redis中
        5、发送短信
        6、返回响应
        :param request:
        :return:
        '''
        mobile = request.GET.get('mobile')
        image_code = request.GET.get('image_code')
        uuid = request.GET.get('uuid')

        if not all([mobile, image_code, uuid]):
            return JsonResponse({'code': RETCODE.NECESSARYPARAMERR, 'errmsg': '缺少必要的参数'})

        redis_conn = get_redis_connection('default')
        redis_image_code = redis_conn.get('img:%s' % uuid)
        if redis_image_code is None:
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图片验证码已过期'})

        try:
            redis_conn.delete('img:%s' % uuid)
        except Exception as e:
            logger.error(e)

        # 比对图片验证码，注意大小写的问题，redis的数据是bytes类型
        if redis_image_code.decode().lower() != image_code.lower():
            return JsonResponse({'code': RETCODE.IMAGECODEERR, 'errmsg': '图片验证码错误'})

        sms_code = "%06d" % randint(0, 999999)
        # 为了以后验证方便，可以将其记录至日志中
        logger.info(sms_code)

        redis_conn.setex('sms:%s' % mobile, 300, sms_code)

        CCP().send_template_sms(mobile, [sms_code, 5], 1)

        return JsonResponse({'code': RETCODE.OK, 'errmsg': '短信发送成功'})


class LoginView(View):

    def get(self, request):
        return render(request, 'login.html')

    def post(self, request):
        '''
        1、接收参数
        2、参数验证
        3、用户认证登录
        4、状态保持
        5、根据用户选择的是否记住登录状态来进行判断
        6、为了首页显示我们需要设置状态进行判断
        7、返回响应
        :param request:
        :return:
        '''
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        remember = request.POST.get('remember')
        # print(mobile,password,remember)
        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('手机号不符合规则')
        if not re.match(r'^[a-zA-Z0-9]{8,20}$', password):
            return HttpResponseBadRequest('密码不符合规则')
        # 采用系统自带的认证方法进行认证
        # 用户名和密码均正确，会返回user对象，否则返回None
        from django.contrib.auth import authenticate
        # 默认认证方法是针对username字段进行用户名的判断，当前使用的是手机号，所以我们需要修改一下认证的字段
        user = authenticate(mobile=mobile, password=password)
        if user is None:
            return HttpResponseBadRequest('用户名或者密码错误')

        from django.contrib.auth import login
        login(request, user)

        # 根据next进行页面跳转
        next_page = request.GET.get('next')
        if next_page:
            response = redirect(next_page)
        else:
            response = redirect(reverse('home:index'))

        if remember == 'on':
            # 默认记住两周
            request.session.set_expiry(None)
            response.set_cookie('is_login', True, max_age=14 * 24 * 3600)
            response.set_cookie('username', user.username, max_age=14 * 24 * 3600)
        else:
            # 浏览器关闭后直接关闭
            request.session.set_expiry(0)
            response.set_cookie('is_login', True)
            response.set_cookie('username', user.username, max_age=14 * 24 * 3600)

        return response


class LogoutView(View):
    def get(self, request):
        '''
        1、session数据删除
        2、删除部分cookie数据
        3、跳转到首页
        :param request:
        :return:
        '''
        logout(request)

        response = redirect(reverse('home:index'))

        response.delete_cookie('is_login')

        return response


class ForgetPasswordView(View):

    def get(self, request):
        return render(request, 'forget_password.html')

    def post(self, request):
        '''
        1、接收数据
        2、验证数据
            2.1 判断数据是否齐全
            2.2 判断数据是否规范
            2.3 短信验证码
        3、根据手机号进行用户信息的查询
        4、如果手机号查出来用户，则修改；没有则进行新用户的创建
        5、跳转到登录页面
        6、返回响应
        :param request:
        :return:
        '''
        mobile = request.POST.get('mobile')
        password = request.POST.get('password')
        password2 = request.POST.get('password2')
        smscode = request.POST.get('sms_code')

        if not all([mobile, password, password2, smscode]):
            return HttpResponseBadRequest('参数不全，请补齐')

        if not re.match(r'^1[3-9]\d{9}$', mobile):
            return HttpResponseBadRequest('手机号不符合规则')

        if not re.match(r'^[0-9a-zA-Z]{8,20}$', password):
            return HttpResponseBadRequest('密码不符合规则')

        if password != password2:
            return HttpResponseBadRequest('两次密码输入不一致')

        redis_conn = get_redis_connection('default')
        redis_sms_code = redis_conn.get('sms:%s' % mobile)

        if redis_sms_code is None:
            return HttpResponseBadRequest('短信验证码已经过期')

        if redis_sms_code.decode() != smscode:
            return HttpResponseBadRequest('短信验证码错误')

        try:
            user = User.objects.get(mobile=mobile)
        except User.DoesNotExist:
            try:
                User.objects.create_user(username=mobile, mobile=mobile, password=password)
            except Exception as e:
                logger.error(e)
                return HttpResponseBadRequest('用户创建失败！')
        else:
            user.set_password(password)
            user.save()

        response = redirect(reverse('Users:login'))

        return response


from django.contrib.auth.mixins import LoginRequiredMixin


# 如果用户未登录，进行默认跳转。默认跳转链接为：accounts/login/?next=xxx
class UserCenterView(LoginRequiredMixin, View):
    def get(self, request):
        user = request.user
        context = {
            'username': user.username,
            'mobile': user.mobile,
            'avatar': user.avatar.url if user.avatar else None,
            'user_desc': user.user_desc
        }
        return render(request, 'center.html', context=context)

    def post(self,request):
        '''
        1、接收参数
        2、将参数保存起来
        3、更新cookie信息
        4、刷新当前页面（重定向操作）
        5、返回响应
        :param request:
        :return:
        '''
        user = request.user
        username = request.POST.get('username',user.username)
        user_desc = request.POST.get('desc')
        avatar = request.FILES.get('avatar')
        try:
            user.username = username
            user.user_desc = user_desc
            if avatar:
                user.avatar = avatar
            user.save()
        except Exception as e:
            logger.error(e)
            return HttpResponseBadRequest('修改失败，请稍后再试')


        response = redirect(reverse('Users:center'))

        response.set_cookie('username',user.username,max_age=14*3600*24)

        return response

class WriteBlogView(LoginRequiredMixin,View):

    def get(self,request):
        #查询所有分类模型
        categories = ArticleCategory.objects.all()

        context = {
            'categories':categories
        }

        return render(request,'write_blog.html',context=context)

