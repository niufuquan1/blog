from django.urls import path
from Users.views import RegisterView

urlpatterns = [
    path('register/',RegisterView.as_view(),name='register'),
]