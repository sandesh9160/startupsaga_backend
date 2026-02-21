from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Count
from django.db.models.functions import TruncDate
from django.utils import timezone
from datetime import timedelta
from .models import Story, Startup

@require_GET
def activity_stats(request):
    """
    Get publication velocity stats for the last 7 days.
    Returns counts of stories and startups published per day.
    """
    # Calculate date range (Today + past 6 days = 7 days total)
    today = timezone.now().date()
    start_date = today - timedelta(days=6)
    
    # Initialize list of dicts for the last 7 days with 0 counts
    # Using a list of days to ensure correct ordering
    days = [(start_date + timedelta(days=i)) for i in range(7)]
    
    # Map for easy lookup: 'Mon': { data... }
    # Note: Using day name as key might cause collisions if range > 1 week, 
    # but for 7 days it guarantees uniqueness of day names (e.g. only one Mon)
    stats_map = {
        d.strftime('%a'): {
            'name': d.strftime('%a'), 
            'stories': 0, 
            'startups': 0,
            'date_obj': d # Keep date object for sorting/matching
        } 
        for d in days
    }
    
    # Query Stories
    story_data = Story.objects.filter(
        published_at__date__gte=start_date,
        published_at__date__lte=today,
        status='published'
    ).annotate(
        day=TruncDate('published_at')
    ).values('day').annotate(
        count=Count('id')
    )

    for entry in story_data:
        day_name = entry['day'].strftime('%a')
        if day_name in stats_map:
            stats_map[day_name]['stories'] = entry['count']

    # Query Startups
    startup_data = Startup.objects.filter(
        created_at__date__gte=start_date,
        created_at__date__lte=today,
        status='published'
    ).annotate(
        day=TruncDate('created_at')
    ).values('day').annotate(
        count=Count('id')
    )

    for entry in startup_data:
        day_name = entry['day'].strftime('%a')
        if day_name in stats_map:
            stats_map[day_name]['startups'] = entry['count']

    # Construct final sorted list based on the original 'days' list order
    result = [stats_map[d.strftime('%a')] for d in days]
    
    # Remove the internal date_obj before sending JSON
    for item in result:
        item.pop('date_obj', None)

    return JsonResponse(result, safe=False)

@require_GET
def platform_stats(request):
    """
    Get global platform stats: total startups and total stories.
    """
    startup_count = Startup.objects.filter(status='published').count()
    story_count = Story.objects.filter(status='published').count()
    unicorn_count = Startup.objects.filter(status='published', funding_stage__iexact='Unicorn').count()

    return JsonResponse({
        'total_startups': startup_count,
        'total_stories': story_count,
        'total_unicorns': unicorn_count
    })
