from django.shortcuts import render, redirect
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from .forms import (UserRegisterForm, UserProfileForm, LifestyleForm, 
                   GoalForm, ProgressRecordForm, FoodCalorieEstimationForm)
from .models import UserProfile, DietPlan, ProgressRecord, FoodCalorieEstimation
from .gemini_client import GeminiClient
import json
from django.conf import settings
import os
import base64
from .utils import get_dietary_status_message
from django.utils import timezone

from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.sessions.models import Session

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import time 


def home(request):
    return render(request, 'nutrition/home.html')

def register(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            username = form.cleaned_data.get('username')
            messages.success(request, f'Account created for {username}! You can now log in.')

            UserProfile.objects.create(user=user)
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'nutrition/register.html', {'form': form})



def logout_user(request):
    logout(request)  # Ends the session and logs out the user

    # Immediately start a new session
    request.session.flush()  # Ensure the session is fully cleared
    request.session.create()  # Start a new session

    messages.info(request, "You've been logged out. Session restarted.")
    return redirect('home')  # Redirect wherever you'd like (home, onboarding, etc.)




@login_required
def profile(request):
    try:
        user_profile = UserProfile.objects.get(user=request.user)
        has_basic_info = all([
            user_profile.height, 
            user_profile.weight, 
            user_profile.age, 
            user_profile.gender
        ])
        has_lifestyle = bool(user_profile.lifestyle)
        has_goal = bool(user_profile.goal)
        
        bmi_category = None
        if user_profile.bmi:
            if user_profile.bmi < 18.5:
                bmi_category = "Underweight"
            elif user_profile.bmi < 25:
                bmi_category = "Normal weight"
            elif user_profile.bmi < 30:
                bmi_category = "Overweight"
            else:
                bmi_category = "Obese"
                
        
        latest_diet_plan = DietPlan.objects.filter(user=request.user).order_by('-date_generated').first()
        
        
        profile_status_message = get_dietary_status_message(user_profile)
        
        context = {
            'user_profile': user_profile,
            'has_basic_info': has_basic_info,
            'has_lifestyle': has_lifestyle,
            'has_goal': has_goal,
            'bmi_category': bmi_category,
            'latest_diet_plan': latest_diet_plan,
            'profile_status_message': profile_status_message
        }
        return render(request, 'nutrition/profile.html', context)
    except UserProfile.DoesNotExist:
        UserProfile.objects.create(user=request.user)
        messages.info(request, "Let's set up your profile to get started!")
        return redirect('user_data')

@login_required
def user_data(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        profile = UserProfile(user=request.user)
    
    if request.method == 'POST':
        form = UserProfileForm(request.POST, instance=profile)
        if form.is_valid():
            user_profile = form.save(commit=False)
            
            user_profile.calculate_bmi()
            user_profile.calculate_bmr()
            user_profile.save()
            
            messages.success(request, "Personal information updated successfully!")
            
            if user_profile.lifestyle:
                return redirect('goals')
            else:
                return redirect('lifestyle')
    else:
        form = UserProfileForm(instance=profile)
    
    return render(request, 'nutrition/user_data.html', {'form': form})

@login_required
def lifestyle(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
        messages.info(request, "Your profile has been created. Please complete your personal information first.")
        return redirect('user_data')
    
    if request.method == 'POST':
        form = LifestyleForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            messages.success(request, "Lifestyle information updated successfully!")
            return redirect('goals')
    else:
        form = LifestyleForm(instance=profile)
    
    return render(request, 'nutrition/lifestyle.html', {'form': form})

@login_required
def goals(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
        messages.info(request, "Your profile has been created. Please complete your personal information first.")
        return redirect('user_data')
    
    if not profile.height or not profile.weight or not profile.age or not profile.gender:
        messages.warning(request, "Please complete your basic information before setting goals.")
        return redirect('user_data')
        
    if not profile.lifestyle:
        messages.warning(request, "Please select your lifestyle before setting goals.")
        return redirect('lifestyle')
    
    if request.method == 'POST':
        form = GoalForm(request.POST, instance=profile)
        if form.is_valid():
            user_profile = form.save(commit=False)
            
            # Calculate daily calories
            user_profile.calculate_daily_calories()
            user_profile.save()
            
            messages.success(request, "Goals updated successfully!")
            return redirect('diet_plan')
    else:
        form = GoalForm(instance=profile)
    
    return render(request, 'nutrition/goals.html', {'form': form})

@login_required
def diet_plan(request):
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        
        messages.info(request, "Please set up your profile to get started.")
        return redirect('user_data') 

    required_fields = [
        profile.height, profile.weight, profile.age, profile.gender,
        profile.lifestyle, profile.goal, profile.diet_preference
    ]
    if not all(required_fields):
        messages.warning(request, "Your profile is incomplete. Please update all required fields (personal info, lifestyle, goal, diet preference) to generate a diet plan.")
        return redirect('profile') 

  
    if not profile.bmi:
        profile.calculate_bmi()
    if not profile.bmr:
        profile.calculate_bmr()
    if not profile.daily_calories:
        profile.calculate_daily_calories()
   
    if not all([profile.bmi, profile.bmr, profile.daily_calories]):
        profile.save() 

    latest_plan = DietPlan.objects.filter(user=request.user).order_by('-date_generated').first()
    error_message = None 

    if request.method == 'POST': 
        if not settings.GEMINI_API_KEY:
            messages.error(request, "Gemini API key is not configured. Please contact the administrator.")
            
            error_message = "Gemini API key is not configured. Cannot generate plan."
            return render(request, 'nutrition/diet_plan.html', {
                'profile': profile,
                'diet_plan': latest_plan, 
                'error': error_message
            })

        try:
            gemini_client = GeminiClient(api_key=settings.GEMINI_API_KEY, model_name=settings.GEMINI_MODEL)

            prompt = f"""
            Generate a personalized daily diet plan for a user with the following characteristics:
- Age: {profile.age} years
- Gender: {profile.get_gender_display()}
- Height: {profile.height} cm
- Weight: {profile.weight} kg
- BMI: {profile.bmi:.2f}
- BMR: {profile.bmr:.0f} calories
- Daily Calorie Target: {profile.daily_calories:.0f}
- Diet Preference: {profile.get_diet_preference_display()}
- Lifestyle: {profile.get_lifestyle_display()}
- Goal: {profile.get_goal_display()}
- Allergies or Disliked Foods: {profile.allergies if profile.allergies else 'None'}

🛑 Important:
Format each meal (Breakfast, Snack, Lunch, etc.) using **Markdown tables** with the following headers:

| Food Item | Portion Size | Calories | Protein (g) | Carbs (g) | Fat (g) |

✅ Example:

## Breakfast (Approx. 400 Calories)
| Food Item | Portion Size | Calories | Protein (g) | Carbs (g) | Fat (g) |
|-----------|--------------|----------|-------------|-----------|---------|
| Oatmeal   | 1 cup        | 150      | 5           | 27        | 3       |
| Banana    | 1 medium     | 100      | 1           | 25        | 0       |

Total: **400 Calories**

🔁 After each meal, provide a section titled “### Alternatives” with 1–2 alternative food suggestions in bullet point format.

⚠️ Do NOT use bullet points for the main meal. Only use markdown tables for them.

The entire plan must:
- Match the calorie target as closely as possible
- Respect diet preferences and allergies
- Be Nepali-style
- Be clearly structured and visually neat

Begin the output with the Calorie Summary like this:
**Estimated Daily Calorie Target: {profile.daily_calories:.0f} Calories**
            """

           
            generated_text = gemini_client.generate_text(prompt)
           

            
            parsed_daily_calories = profile.daily_calories 
            try:
                for line in generated_text.split('\n'):
                    if "estimated daily calorie target:" in line.lower():
                       
                        import re
                        match = re.search(r'(\d+)\s*calories', line.lower())
                        if match:
                            parsed_daily_calories = int(match.group(1))
                            break
            except Exception as e:
                print(f"Could not parse calories from Gemini response: {e}")
               

           
            if latest_plan: 
                latest_plan.diet_plan = generated_text 
                latest_plan.daily_calories = parsed_daily_calories
                latest_plan.date_generated = timezone.now()
                latest_plan.save()
            else: 
                latest_plan = DietPlan.objects.create(
                    user=request.user,
                    diet_plan=generated_text, 
                    daily_calories=parsed_daily_calories,
                    date_generated=timezone.now()
                )
            
            messages.success(request, "New diet plan generated successfully!")
            return redirect('diet_plan')

        except Exception as e:
            
            error_message = f"An error occurred while generating the diet plan: {str(e)}"
            messages.error(request, error_message)
            print(f"Error in diet_plan generation: {e}") 

    
    return render(request, 'nutrition/diet_plan.html', {
        'profile': profile,
        'diet_plan': latest_plan,
        'error': error_message 
    })

@login_required
def track_progress(request):
    # Get user profile
    try:
        profile = UserProfile.objects.get(user=request.user)
    except UserProfile.DoesNotExist:
        profile = UserProfile.objects.create(user=request.user)
        messages.info(request, "Your profile has been created. Please complete your personal information first.")
        return redirect('user_data')
    
    # Get progress records
    progress_records = ProgressRecord.objects.filter(user=request.user).order_by('-date')[:10]
    
    context = {
        'profile': profile,
        'progress_records': progress_records
    }
    
    return render(request, 'nutrition/track_progress.html', context)

@login_required
def add_progress(request):
    if request.method == 'POST':
        form = ProgressRecordForm(request.POST)
        if form.is_valid():
            progress = form.save(commit=False)
            progress.user = request.user
            progress.save()
            
            # Update user profile weight
            try:
                profile = UserProfile.objects.get(user=request.user)
                profile.weight = progress.weight
                profile.calculate_bmi()  # Recalculate BMI with new weight
                profile.save()
            except UserProfile.DoesNotExist:
                profile = UserProfile.objects.create(user=request.user, weight=progress.weight)
                profile.calculate_bmi()
                profile.save()
            
            messages.success(request, "Progress recorded successfully!")
            return redirect('track_progress')
    else:
        form = ProgressRecordForm()
    
    # Get progress records for display
    progress_records = ProgressRecord.objects.filter(user=request.user).order_by('-date')[:10]
    
    context = {
        'form': form,
        'progress_records': progress_records
    }
    
    return render(request, 'nutrition/track_progress.html', context)

@login_required
def progress_data(request):
    """API endpoint to get progress data for charts"""
    progress_records = ProgressRecord.objects.filter(user=request.user).order_by('date')
    
    dates = [record.date.strftime('%Y-%m-%d') for record in progress_records]
    weights = [float(record.weight) for record in progress_records]
    calories = [record.calories_consumed for record in progress_records if record.calories_consumed]
    
    data = {
        'dates': dates,
        'weights': weights,
        'calories': calories
    }
    
    return JsonResponse(data)

@login_required
def calorie_estimation(request):
    # Verify we have the API key before processing
    if not settings.GEMINI_API_KEY:
        messages.error(request, "Gemini API key is not configured. Please contact the administrator.")
        return redirect('profile')
        
    if request.method == 'POST':
        form = FoodCalorieEstimationForm(request.POST, request.FILES)
        if form.is_valid():
            # Save the form but don't commit yet
            food_record = form.save(commit=False)
            food_record.user = request.user
            
            # Read the image file
            image_file = request.FILES['food_image']
            image_data = image_file.read()
            
            # Encode image to base64
            base64_image = base64.b64encode(image_data).decode('utf-8')
            
            try:
                # Initialize Gemini client
                gemini_client = GeminiClient(api_key=settings.GEMINI_API_KEY, model_name=settings.GEMINI_MODEL)
                
                # Prepare prompt for image analysis
                description = form.cleaned_data.get('description', '')
                portion = form.cleaned_data.get('portion', '')
                
                prompt = f"""
                Analyze this food image and provide:
                1. An estimated calorie count for the entire dish
                2. Breakdown of macronutrients (protein, carbs, fat)
                3. List of main ingredients identified
                
                Additional information provided by user:
                - Description: {description}
                - Portion: {portion}
                
                Format your response clearly with sections for Calories, Macronutrients, and Ingredients.
                """
                
                # Generate analysis using Gemini
                result = gemini_client.analyze_image(base64_image, prompt)
                
                # Parse the results - extract estimated calories (assuming the response contains this information)
                # This is a simple extraction that would need to be refined based on actual API responses
                calorie_info = None
                if "calories" in result.lower():
                    for line in result.split('\n'):
                        if "calories" in line.lower():
                            try:
                                # Try to extract the number preceding "calories"
                                import re
                                calorie_match = re.search(r'(\d+)\s*(?:to\s*\d+)?\s*calories', line.lower())
                                if calorie_match:
                                    calorie_info = int(calorie_match.group(1))
                            except:
                                pass
                
                # Save the details
                food_record.estimated_calories = calorie_info
                food_record.nutrition_details = result
                food_record.save()
                
                messages.success(request, "Food calorie estimation completed!")
                
                return render(request, 'nutrition/calorie_estimation.html', {
                    'form': FoodCalorieEstimationForm(),
                    'result': result,
                    'food_record': food_record
                })
                
            except Exception as e:
                messages.error(request, f"Error analyzing food: {str(e)}")
    else:
        form = FoodCalorieEstimationForm()
    
    # Get recent estimations
    recent_estimations = FoodCalorieEstimation.objects.filter(
        user=request.user
    ).order_by('-date')[:5]
    
    return render(request, 'nutrition/calorie_estimation.html', {
        'form': form,
        'recent_estimations': recent_estimations
    })


@csrf_exempt
def generate_planner(request):
    if request.method == 'POST':
        # Simulate long task (like calling Gemini API)
        time.sleep(3)
        planner_text = "✅ Your personalized diet plan:\n- Breakfast: Poha\n- Lunch: Dal Bhat\n- Dinner: Light Khichdi"
        return JsonResponse({'plan': planner_text})
    return JsonResponse({'error': 'Invalid request'}, status=400)