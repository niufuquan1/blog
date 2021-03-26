from django.shortcuts import render

# Create your views here.
from django.views import View
from django.http import HttpResponseBadRequest, HttpResponse
from libs.captcha.captcha import captcha
from django_redis import get_redis_connection


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
