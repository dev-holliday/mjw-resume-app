from asyncio import log
from django.shortcuts import render, redirect
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
import json

def index(request):
    print('Request for index page received')
    return render(request, 'hello_azure/index.html')

@csrf_exempt
def resume(request):
    if request.method == 'POST':
        name = "Matthew Weigand"  # Fixed name for resume viewing
        
        if name is None or name == '':
            print("Request for resume page received with no name or blank name -- redirecting")
            return redirect('index')
        else:
            print("Request for resume page received with name=%s" % name)
            context = {'name': name }
            return render(request, 'hello_azure/resume.html', context)
    else:
        return redirect('index')
    
@csrf_exempt
def employer_view(request):
    if request.method == 'POST':
        # Placeholder for employer sign-in logic
        print("Employer sign-in request received")
        return render(request, 'hello_azure/resume_employer.html')
    else:
        return render(request, 'hello_azure/resume_employer.html')

@csrf_exempt
def api_resume_data(request):
    """API endpoint to return resume data as JSON"""
    if request.method == 'GET':
        resume_data = {
            'name': 'Matthew Weigand',
            'title': 'Lead Digital Engineer',
            'location': 'Milwaukee, WI',
            'email': 'weigand43@gmail.com',
            'phone': '(260) 467-3453',
            'summary': 'Software Engineer with over 5 years of experience developing enterprise systems, microservices, and automation tools with Kotlin, Java, C#, and Python.',
            'skills': [
                'Java/Kotlin',
                'C#',
                'Python',
                'Spring Boot',
                'Angular',
                'PostgreSQL'
            ],
            'experience': [
                {
                    'title': 'Lead Digital Engineer',
                    'company': 'Sonata Software North America Inc.',
                    'client': 'Bluestem Brands',
                    'period': 'April 2023 – September 2025'
                },
                {
                    'title': 'Software Developer',
                    'company': 'Genesis10',
                    'client': 'Bluestem Brands',
                    'period': 'March 2022 – April 2023'
                }
            ]
        }
        return JsonResponse(resume_data)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def api_contact(request):
    """API endpoint to handle contact form submissions"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = data.get('name', '')
            email = data.get('email', '')
            message = data.get('message', '')
            
            # Validate input
            if not name or not email or not message:
                return JsonResponse(
                    {'error': 'Name, email, and message are required'},
                    status=400
                )
            
            # Log the contact submission
            print(f"Contact form received - Name: {name}, Email: {email}, Message: {message}")
            
            # Here you could save to database, send email, etc.
            # For now, just return success
            return JsonResponse({
                'success': True,
                'message': 'Thank you for reaching out! I will get back to you soon.'
            })
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON'}, status=400)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)