from django.urls import path
from . import views

urlpatterns = [
    path('', views.index, name='index'),
    path('resume', views.resume, name='resume'),
    path('employer', views.employer_view, name='employer_view'),
    path('api/hello', views.api_resume_data, name='api_resume'),
    path('api/contact', views.api_contact, name='api_contact'),
]