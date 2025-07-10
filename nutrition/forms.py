from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import User
from .models import UserProfile, ProgressRecord, FoodCalorieEstimation
import dns.resolver
from email_validator import validate_email, EmailNotValidError, EmailUndeliverableError
import logging

logger = logging.getLogger(__name__)

class UserRegisterForm(UserCreationForm):
    email = forms.EmailField()

    class Meta:
        model = User
        fields = ['username', 'email', 'password1', 'password2']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add placeholders and styling to form fields
        self.fields['username'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Username',
            'required': True
        })

        self.fields['email'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Email address',
            'required': True
        })

        self.fields['password1'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Password',
            'required': True
        })

        self.fields['password2'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'Confirm password',
            'required': True
        })

        # Remove help text for cleaner appearance
        self.fields['username'].help_text = None
        self.fields['password1'].help_text = None
        self.fields['password2'].help_text = None
        
    def clean_email(self):
        """
        Comprehensive email validation:
        1. Check for proper email format
        2. Verify domain exists and has valid MX records
        3. Normalize the email for consistent storage
        """
        email = self.cleaned_data.get('email')
        
        if not email:
            raise forms.ValidationError("Email address is required.")
            
        # Check if another user already uses this email
        if User.objects.filter(email=email).exists():
            raise forms.ValidationError("This email address is already in use.")
            
        try:
            # Validate and normalize the email
            # This checks format and performs DNS lookups
            valid = validate_email(email, check_deliverability=True)
            normalized_email = valid.normalized
            
            # Additional verification
            domain = normalized_email.split('@')[1]
            
            # Get MX records for the domain
            try:
                mx_records = dns.resolver.resolve(domain, 'MX')
                if not mx_records:
                    raise forms.ValidationError("This email domain doesn't have valid mail servers.")
            except Exception as e:
                logger.warning(f"MX record check failed for {domain}: {str(e)}")
                raise forms.ValidationError(
                    "We couldn't verify the email domain. Please check your email address."
                )
                
            return normalized_email
            
        except EmailNotValidError as e:
            # Format error
            raise forms.ValidationError(f"Invalid email format: {str(e)}")
            
        except EmailUndeliverableError as e:
            # Deliverability error (domain doesn't exist or no valid MX records)
            raise forms.ValidationError(f"Email address appears to be undeliverable: {str(e)}")
            
        except Exception as e:
            # Catch any other errors
            logger.error(f"Email validation error: {str(e)}")
            raise forms.ValidationError("Email validation failed. Please provide a valid email address.")

class UserProfileForm(forms.ModelForm):
    GENDER_CHOICES = [
        ('M', 'Male'),
        ('F', 'Female'),
    ]

    DIET_PREFERENCE_CHOICES = [
        ('veg', 'Vegetarian'),
        ('non-veg', 'Non-Vegetarian'),
    ]

    gender = forms.ChoiceField(choices=GENDER_CHOICES, widget=forms.RadioSelect)
    diet_preference = forms.ChoiceField(choices=DIET_PREFERENCE_CHOICES, widget=forms.RadioSelect)
    allergies = forms.CharField(widget=forms.Textarea, required=False)

    class Meta:
        model = UserProfile
        fields = ['height', 'weight', 'age', 'gender', 'diet_preference', 'allergies']

class LifestyleForm(forms.ModelForm):
    LIFESTYLE_CHOICES = [
        ('sedentary', 'Sedentary (little or no exercise)'),
        ('lightly_active', 'Lightly Active (light exercise/sports 1-3 days/week)'),
        ('moderately_active', 'Moderately Active (moderate exercise/sports 3-5 days/week)'),
        ('very_active', 'Very Active (hard exercise/sports 6-7 days a week)'),
        ('athletic', 'Athletic (very hard exercise, training, or physical job)')
    ]

    lifestyle = forms.ChoiceField(choices=LIFESTYLE_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = UserProfile
        fields = ['lifestyle']

class GoalForm(forms.ModelForm):
    GOAL_CHOICES = [
        ('maintain', 'Maintain current weight'),
        ('lose', 'Lose weight'),
        ('gain', 'Gain weight/bulk up'),
        ('cut', 'Cut (lose fat while preserving muscle)')
    ]

    goal = forms.ChoiceField(choices=GOAL_CHOICES, widget=forms.RadioSelect)

    class Meta:
        model = UserProfile
        fields = ['goal']

class ProgressRecordForm(forms.ModelForm):
    class Meta:
        model = ProgressRecord
        fields = ['weight', 'calories_consumed', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

class FoodCalorieEstimationForm(forms.ModelForm):
    class Meta:
        model = FoodCalorieEstimation
        fields = ['food_image', 'description', 'portion']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Describe the ingredients used in your meal'}),
            'portion': forms.TextInput(attrs={'placeholder': 'e.g., 1 cup, 200g, 1 serving'})
        }
