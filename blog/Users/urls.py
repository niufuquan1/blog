from django.urls import path
from Users.views import RegisterView, ImageCodeView, SmsCodeView, LoginView, LogoutView

urlpatterns = [
    path('register/',RegisterView.as_view(),name='register'),
    #图片验证码
    path('imagecode/',ImageCodeView.as_view(),name='imagecode'),
    #短信验证码
    path('smscode/',SmsCodeView.as_view(),name='smscode'),

    path('login/',LoginView.as_view(),name='login'),

    path('logout/',LogoutView.as_view(),name='logout'),

]