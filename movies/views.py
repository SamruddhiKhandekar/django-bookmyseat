from django.shortcuts import render, redirect ,get_object_or_404
from .models import Movie,Theater,Seat,Booking,Genre
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.conf import settings
import stripe
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
from django.core.mail import send_mail
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count

stripe.api_key=settings.STRIPE_SECRET_KEY

price_per_seat = 200

def movie_list(request):
    movies = Movie.objects.all()
    search_query=request.GET.get('search')
    if search_query:
        movies=Movie.objects.filter(name__icontains=search_query)
    language=request.GET.get('language')
    if language:
        movies=movies.filter(language=language)
    genre_id=request.GET.get("genres")
    if genre_id:
        movies=movies.filter(genres__id=genre_id)
    return render(request,'movies/movie_list.html',{'movies':movies, 'all_genres':Genre.objects.all(),})

def movie_detail(request,movie_id):
    movie=get_object_or_404(Movie, id=movie_id)
    return render(request,'movies/movie_detail.html',{'movie':movie}) 

def theater_list(request,movie_id):
    movie = get_object_or_404(Movie, id=movie_id)
    theater=Theater.objects.filter(movie=movie)
    return render(request,'movies/theater_list.html',{'movie':movie,'theaters':theater})


@login_required(login_url='/login/')
def book_seats(request,theater_id):
    theater=get_object_or_404(Theater, id=theater_id)
    seats=Seat.objects.filter(theater=theater)
    for seat in seats:
        if seat.reservation_expired():
            seat.is_reserved = False
            seat.reserved_at = None
            seat.save()
            

    if request.method=='POST':
        selected_seats= request.POST.getlist('seats')
        error_seats=[]
        if not selected_seats:
            return render(request,"movies/seat_selection.html",{
                'theater':theater,
                "seats":seats,
                'error':"No seat selected"
                })
        
        for seat_id in selected_seats:
            seat = Seat.objects.get(id=seat_id)
            seat.is_reserved = True
            seat.reserved_at = timezone.now()
            seat.save()

        request.session['selected_seats'] = selected_seats
        request.session['theater_id'] = theater.id
        request.session['movie_id'] = theater.movie.id
        request.session['total_price'] = price_per_seat * len(selected_seats)

        return redirect('payment_page')
    
    return render(request,'movies/seat_selection.html',{
        'theater':theater,
        'seats':seats
    })

@login_required
def payment_page(request):
    selected_seats = request.session.get('selected_seats')
    theater_id = request.session.get('theater_id')
    movie_id = request.session.get('movie_id')
    total_price = request.session.get('total_price')

    if not selected_seats:
        return redirect(movie_list)
    
    movie = Movie.objects.get(id=movie_id)

    return render(request,'movies/payment.html',{
        'movie':movie,
        'price':total_price,
        'stripe_public_key': settings.STRIPE_PUBLIC_KEY
    })

@csrf_exempt
@login_required
def create_checkout_session(request):
    if request.method == "POST":
        movie_name = request.POST["movie_name"]
        price = int(float(request.POST["price"])*100) 
        
        session =  stripe.checkout.Session.create(
            payment_method_types = ["card"],
            line_items = [{
                "price_data":{
                    "currency":"inr",
                    "product_data": {"name":movie_name},
                    "unit_amount":price,
                },
                "quantity":1,
            }],
            mode="payment",
            success_url=request.build_absolute_uri("/movies/payment-success/"),
            cancel_url=request.build_absolute_uri("/movies/payment-failed/"),
        )
        
        return JsonResponse({"id": session.id})
    
@login_required
def payment_success(request):
    selected_seats = request.session.get('selected_seats')
    theater_id = request.session.get('theater_id')
    movie_id = request.session.get('movie_id')

    if not selected_seats:
        return redirect(movie_list)
    
    theater = Theater.objects.get(id=theater_id)
    movie = Movie.objects.get(id=movie_id)

    booked_seat_numbers = []
    timeout_occurred = False

    for seat_id in selected_seats:
        seat = Seat.objects.get(id=seat_id)

        if seat.reservation_expired():
            timeout_occurred = True
            seat.is_reserved = False
            seat.reserved_at = None
            seat.save()
            continue

        if not seat.is_booked:
            Booking.objects.create(
                user=request.user,
                seat=seat,
                movie=movie,
                theater=theater
            )
            seat.is_booked = True
            seat.is_reserved = False
            seat.reserved_at = None
            seat.save()
            booked_seat_numbers.append(seat.seat_number)

    message = f"""
    Booking Confirmed
    Movie: {movie.name}
    Theatre: {theater.name}
    Show Time: {theater.time}
    Seats: {",".join(booked_seat_numbers)}

    Enjoy Your Movie
    """

    send_mail(
        subject="Movie Ticket Confirmation",
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[request.user.email],
        fail_silently=False,
    )
    
    for key in ['selected_seats', 'theater_id', 'movie_id', 'total_price']:
        if key in request.session:
            del request.session[key]

    if timeout_occurred:
        return render(request, 'movies/payment_timeout.html')

    return render(request,'movies/payment_success.html',{
        "seats": booked_seat_numbers,
        "movie_name":movie.name,
        "theater_name":theater.name,
    })

@login_required
def payment_failed(request):
    return render(request,'movies/payment_failed.html')

@staff_member_required
def admin_dashboard(request):
    
    total_revenue = Booking.objects.count() * price_per_seat

    popular_movies = (
        Movie.objects
        .annotate(total_bookings = Count('booking'))
        .order_by('-total_bookings')
    )

    busiest_theaters = (
        Theater.objects
        .annotate(total_bookings = Count('booking'))
        .order_by('-total_bookings')
    )

    return render(request,'admin/admin_dashboard.html',{'total_revenue': total_revenue, 'popular_movies': popular_movies, 'busiest_theaters': busiest_theaters})