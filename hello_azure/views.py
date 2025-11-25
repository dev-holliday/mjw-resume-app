from asyncio import log
from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

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