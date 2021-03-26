from django.urls import path
from Users.views import RegisterView, ImageCodeView

urlpatterns = [
    path('register/',RegisterView.as_view(),name='register'),
    #图片验证码
    path('imagecode/',ImageCodeView.as_view(),name='imagecode'),

]