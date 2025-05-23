from django.urls import path
from . import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('', views.home, name='home'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='nutrition/login.html'), name='login'),
    
    path('profile/', views.profile, name='profile'),
    path('user_data/', views.user_data, name='user_data'),
    path('lifestyle/', views.lifestyle, name='lifestyle'),
    path('goals/', views.goals, name='goals'),
    path('diet_plan/', views.diet_plan, name='diet_plan'),
    path('track_progress/', views.track_progress, name='track_progress'),
    path('add_progress/', views.add_progress, name='add_progress'),
    path('calorie_estimation/', views.calorie_estimation, name='calorie_estimation'),
    path('api/progress_data/', views.progress_data, name='progress_data'),
    path('logout/', views.logout_user, name='logout'),
    path('generate-planner/', views.generate_planner, name='generate_planner'),
        path('aboutus/', views.aboutus, name='aboutus'),
    path('how-it-works/', views.how_it_works, name='how_it_works'),
    path('chatbot/', views.chatbot, name='chatbot'),
]
