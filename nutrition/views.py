from django.shortcuts import render, redirect, get_object_or_404
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
import google.generativeai as genai

from django.contrib.auth import logout
from django.contrib import messages
from django.shortcuts import redirect
from django.contrib.sessions.models import Session

from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import time 
import csv

def load_food_data():
    """
    Load food data from Food Data.csv file
    Returns a dictionary with food names as keys and nutritional info as values
    """
    food_data = {}
    csv_file_path = os.path.join(settings.BASE_DIR, 'Food Data.csv')
    
    try:
        with open(csv_file_path, 'r', encoding='utf-8') as file:
            csv_reader = csv.DictReader(file)
            for row in csv_reader:
                # Skip empty rows
                if not row.get('Food Name') or row['Food Name'].strip() == '':
                    continue
                
                food_name = row['Food Name'].strip()
                
                # Handle different possible column names
                calories = row.get('Calories (kcal)', row.get('Calories', '')).strip()
                carbs = row.get('Carbohydrates (g)', row.get('Carbs (g)', row.get('Carbs', ''))).strip()
                protein = row.get('Protein (g)', row.get('Protein', '')).strip()
                fats = row.get('Fats (g)', row.get('Fat (g)', row.get('Fats', row.get('Fat', '')))).strip()
                
                # Clean up the data (remove ~, commas, etc.)
                calories = calories.replace('~', '').replace(',', '') if calories else '0'
                carbs = carbs.replace('~', '').replace(',', '') if carbs else '0'
                protein = protein.replace('~', '').replace(',', '') if protein else '0'
                fats = fats.replace('~', '').replace(',', '') if fats else '0'
                
                food_data[food_name.lower()] = {
                    'name': food_name,
                    'category': row.get('Category', '').strip(),
                    'serving_size': row.get('Typical Serving Size', row.get('Serving Size', '')).strip(),
                    'calories': calories,
                    'carbs': carbs,
                    'protein': protein,
                    'fats': fats,
                    'fiber': row.get('Fiber (g)', row.get('Fiber', '')).strip(),
                    'micronutrients': row.get('Micronutrients', row.get('Key Micronutrients', '')).strip(),
                    'preparation_notes': row.get('Preparation Notes', '').strip()
                }
    except FileNotFoundError:
        print(f"Food Data.csv file not found at {csv_file_path}")
        return {}
    except Exception as e:
        print(f"Error reading Food Data.csv: {e}")
        return {}
    
    return food_data

def get_food_nutrition(food_name, food_data):
    """
    Get nutritional information for a specific food item
    Returns the food data if found, None otherwise
    """
    food_name_lower = food_name.lower().strip()
    
    # Direct match
    if food_name_lower in food_data:
        return food_data[food_name_lower]
    
    # Partial match (check if food name contains the search term)
    for key, value in food_data.items():
        if food_name_lower in key or key in food_name_lower:
            return value
    
    return None

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
            # Extract email-specific errors to display them more prominently
            email_errors = form.errors.get('email', None)
            if email_errors:
                for error in email_errors:
                    messages.error(request, f"Email error: {error}")
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

            # Load food data from CSV
            food_data = load_food_data()
            
            if not food_data:
                messages.warning(request, "Food database could not be loaded. Using default nutritional values.")
                print("Warning: Food Data.csv not found or could not be read")
            
            print(f"Loaded {len(food_data)} foods from Food Data.csv")
            
            # Create a list of available Nepali foods for the AI to choose from
            nepali_foods = []
            for food_name, food_info in food_data.items():
                if food_info['calories'] and food_info['calories'].isdigit():
                    nepali_foods.append({
                        'name': food_info['name'],
                        'calories': food_info['calories'],
                        'carbs': food_info['carbs'] if food_info['carbs'] else '0',
                        'protein': food_info['protein'] if food_info['protein'] else '0',
                        'fats': food_info['fats'] if food_info['fats'] else '0',
                        'serving_size': food_info['serving_size'],
                        'category': food_info['category']
                    })
            
            print(f"Processed {len(nepali_foods)} foods with valid nutritional data")

            # Filter foods based on diet preference
            if profile.diet_preference == 'veg':
                nepali_foods = [food for food in nepali_foods if 'meat' not in food['name'].lower() and 'chicken' not in food['name'].lower() and 'buffalo' not in food['name'].lower() and 'mutton' not in food['name'].lower() and 'pork' not in food['name'].lower() and 'goat' not in food['name'].lower()]

            # Create food database string for the prompt
            food_database = "Available Nepali Foods with Nutritional Information:\n"
            for food in nepali_foods[:50]:  # Limit to first 50 foods to avoid token limits
                food_database += f"- {food['name']}: {food['serving_size']}, {food['calories']} cal, {food['carbs']}g carbs, {food['protein']}g protein, {food['fats']}g fat ({food['category']})\n"

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

{food_database}

🛑 Important Instructions:
1. **PRIORITIZE FOODS FROM THE PROVIDED DATABASE** - Use the exact food names and nutritional values from the database above
2. If a food is not in the database, you can suggest other Nepali foods but use approximate nutritional values
3. Format each meal (Breakfast, Snack, Lunch, etc.) using **Markdown tables** with the following headers:

| Food Item | Portion Size | Calories | Protein (g) | Carbs (g) | Fat (g) |

✅ Example:

## Breakfast (Approx. 400 Calories)
| Food Item | Portion Size | Calories | Protein (g) | Carbs (g) | Fat (g) |
|-----------|--------------|----------|-------------|-----------|---------|
| Dal Bhat  | 1 plate      | 450      | 14          | 70        | 10      |
| Banana    | 1 medium     | 100      | 1           | 25        | 0       |

Total: **550 Calories**

🔁 After each meal, provide a section titled "### Alternatives" with 1–2 alternative food suggestions from the database in bullet point format.

⚠️ Do NOT use bullet points for the main meal. Only use markdown tables for them.

The entire plan must:
- Match the calorie target as closely as possible
- Respect diet preferences and allergies
- Be Nepali-style using foods from the database when possible
- Be clearly structured and visually neat

Begin the output with the Calorie Summary like this:
**Estimated Daily Calorie Target: {profile.daily_calories:.0f} Calories**
            """

           
            # Generate the diet plan
            generated_text = gemini_client.generate_text(prompt)
            
            # Validate and improve the generated plan with accurate nutritional data
            generated_text = validate_and_improve_diet_plan(generated_text, food_data, profile)
           

            
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


def aboutus(request):
    return render(request, 'nutrition/aboutus.html')

def how_it_works(request):
    return render(request, 'nutrition/how-it-works.html')

@login_required
def chat(request):
    return render(request, 'nutrition/chat.html')

@csrf_exempt
@login_required
def chatbot_api(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            user_message = data.get('message', '')
            chat_history = data.get('chat_history', [])
            user_profile = data.get('user_profile', None)
            
            # Configure Google API
            GOOGLE_API_KEY = "AIzaSyD2JrW72oo2aRwOIhDNNgoQ7FSNfv67lRQ"
            genai.configure(api_key=GOOGLE_API_KEY)
            model = genai.GenerativeModel('gemini-2.5-flash-preview-04-17')
            
            # Format chat history
            chat_history_string = "No previous conversation turns in this session yet."
            if chat_history:
                formatted_history = []
                for msg in chat_history[-6:]:  # Last 3 turns (user + assistant)
                    role = "User" if msg["role"] == "user" else "Assistant"
                    formatted_history.append(f"{role}: {msg['content']}")
                chat_history_string = "\n".join(formatted_history)
            
            # Format user profile
            user_profile_details_string = "No profile information provided by the user yet."
            if user_profile:
                bmi, bmr = calculate_health_metrics(
                        user_profile['weight_kg'],
                        user_profile['height_cm'],
                        user_profile['age'],
                        user_profile['gender']
                    )

                tdee = calculate_tdee(bmr, user_profile['activity_level']) if bmr is not None else None
                
                details = [
                    f"Name: {user_profile['name']}",
                    f"Age: {user_profile['age']} years",
                    f"Height: {user_profile['height_cm']} cm",
                    f"Weight: {user_profile['weight_kg']} kg",
                    f"Gender: {user_profile['gender'].title()}",
                    f"Activity Level: {user_profile['activity_level']}"
                ]
                
                if bmi is not None:
                    details.append(f"BMI: {bmi}")
                if bmr is not None:
                    details.append(f"BMR: {bmr} kcal/day")
                if tdee is not None:
                    details.append(f"TDEE: {tdee} kcal/day")
                
                user_profile_details_string = "\n".join(details)
            
            # System prompt template
            SYSTEM_PROMPT_TEMPLATE = """You are a friendly, encouraging, and expert Nepali Nutrition & Wellness Assistant. 
Your primary goal is to help users with their nutrition, diet plans, and promote a healthy lifestyle with a strong focus on Nepali cuisine and culture. 
Your tone should be positive, supportive, and natural, like a knowledgeable friend. *Your responses should be very concise, like short chat messages. Aim for 1-3 sentences per turn unless providing a list or steps.*

*Chat History (Recent Turns):*
{chat_history}

*User Profile Information:*
{user_profile_details}

Based on all the above (including chat history if relevant), please answer the user's current question. Remember: be concise, natural, conversational, and use installments for longer answers, always checking if the user wants to proceed.
User Question: {user_question}
Answer:"""
            
            final_prompt = SYSTEM_PROMPT_TEMPLATE.format(
                chat_history=chat_history_string,
                user_profile_details=user_profile_details_string,
                user_question=user_message
            )
            
            response = model.generate_content(final_prompt)
            assistant_response = response.text
            
            return JsonResponse({
                'message': assistant_response
            })
            
        except Exception as e:
            return JsonResponse({
                'error': str(e)
            }, status=500)
    
    return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

@login_required
def book_appointment(request):
    if request.method == 'POST':
        messages.success(request, 'Your appointment request has been submitted successfully!')
        return redirect('diet_plan')
    return render(request, 'nutrition/book_appointment.html')

@login_required
def disease(request):
    user_profile = get_object_or_404(UserProfile, user=request.user)
    
    if request.method == 'POST':
        user_profile.diseases = request.POST.get('diseases', '')
        user_profile.medications = request.POST.get('medications', '')
        user_profile.dietary_restrictions = request.POST.get('dietary_restrictions', '')
        user_profile.save()
        messages.success(request, 'Disease management information updated successfully.')
        return redirect('disease')
    
    return render(request, 'nutrition/disease.html', {
        'user_profile': user_profile,
    })

def validate_and_improve_diet_plan(generated_text, food_data, profile):
    """
    Validate and improve the generated diet plan by cross-referencing with food database
    """
    try:
        # Split the generated text into lines
        lines = generated_text.split('\n')
        improved_lines = []
        
        for line in lines:
            # Check if this line contains a food item in a table
            if '|' in line and any(food_name in line.lower() for food_name in food_data.keys()):
                # Try to find and replace with accurate nutritional data
                for food_name, food_info in food_data.items():
                    if food_name in line.lower():
                        # Extract the portion size from the line
                        parts = line.split('|')
                        if len(parts) >= 3:
                            food_item = parts[1].strip()
                            portion_size = parts[2].strip()
                            
                            # Use the exact nutritional values from the database
                            calories = food_info['calories'] if food_info['calories'] else '0'
                            carbs = food_info['carbs'] if food_info['carbs'] else '0'
                            protein = food_info['protein'] if food_info['protein'] else '0'
                            fats = food_info['fats'] if food_info['fats'] else '0'
                            
                            # Reconstruct the line with accurate data
                            improved_line = f"| {food_info['name']} | {food_info['serving_size']} | {calories} | {protein} | {carbs} | {fats} |"
                            improved_lines.append(improved_line)
                            break
                else:
                    # If no match found, keep the original line
                    improved_lines.append(line)
            else:
                # Keep non-table lines as they are
                improved_lines.append(line)
        
        return '\n'.join(improved_lines)
    except Exception as e:
        print(f"Error validating diet plan: {e}")
        return generated_text

def test_food_data(request):
    """
    Test function to verify food data loading (for debugging)
    """
    food_data = load_food_data()
    
    if food_data:
        # Show first 5 foods as a test
        test_foods = list(food_data.items())[:5]
        result = "Food Data loaded successfully!\n\nFirst 5 foods:\n"
        for food_name, food_info in test_foods:
            result += f"- {food_info['name']}: {food_info['calories']} cal, {food_info['carbs']}g carbs, {food_info['protein']}g protein, {food_info['fats']}g fat\n"
    else:
        result = "Failed to load food data from CSV file."
    
    return JsonResponse({'result': result, 'total_foods': len(food_data)})
