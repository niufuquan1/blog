from django.shortcuts import render

# Create your views here.
from django.views import View
from django.http import HttpResponseBadRequest, HttpResponse, JsonResponse
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
