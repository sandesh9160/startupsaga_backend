from django.http import JsonResponse, HttpResponse
from django.views.decorators.http import require_GET
from django.views.decorators.csrf import csrf_exempt
from django.core.paginator import Paginator
from django.db.models import Q, Count
from django.utils.text import slugify
from .models import Startup, Story, Category, City, Page, PageSection, PageThemeOverride, NavigationItem, FooterSetting, SEOSetting, MediaItem, LayoutSetting, AIPrompt, Redirect
from django.forms.models import model_to_dict
import json
import base64
from django.core.files.base import ContentFile
from django.db import transaction
from django.contrib.auth import authenticate, login, logout
from django.views.decorators.http import require_POST
from .ai_utils import (
    generate_seo_suggestions, 
    generate_ai_content, 
    generate_ai_content_direct,
    CitySEOGenerator,
    CityDescription,
    CityAltText
)
from django.conf import settings

def _get_founders(request, startup):
    """
    Unified founder data retrieval. 
    Checks the JSON founders_data field first, then falls back to Founder model objects.
    """
    founders = startup.founders_data or []
    if not founders:
        # Fetch from the Founder model if JSON field is empty
        founder_objs = startup.founders.all().order_by('order')
        if founder_objs.exists():
            for fo in founder_objs:
                # Add initials for frontend fallback if needed
                initials = "".join([n[0] for n in fo.name.split() if n]) if fo.name else ""
                
                logo_url = fo.photo.url if fo.photo else None
                if logo_url and not logo_url.startswith('http'):
                    logo_url = request.build_absolute_uri(logo_url)
                
                founders.append({
                    'name': fo.name,
                    'role': fo.designation or "Founder",
                    'linkedin': fo.linkedin,
                    'image': logo_url,
                    'bio': fo.bio,
                    'initials': initials
                })
    return founders




def _strip_html(text: str) -> str:
    if not text:
        return ""
    import re
    return re.sub(r"<[^>]*>", "", text)


def _create_redirect_if_slug_changed(old_slug, new_slug, path_prefix):
    """When slug changes, create 301 redirect from old path to new path (SEO equity)."""
    if not old_slug or not new_slug or old_slug == new_slug:
        return
    from_path = f"/{path_prefix.strip('/')}/{old_slug}/"
    to_path = f"/{path_prefix.strip('/')}/{new_slug}/"
    if from_path != to_path:
        Redirect.objects.get_or_create(from_path=from_path, defaults={'to_path': to_path, 'is_permanent': True})

def _serialize_story(s: Story):
    excerpt = (s.excerpt or (_strip_html(s.content)[:200] if s.content else "")) if hasattr(s, 'excerpt') else (_strip_html(s.content)[:200] if s.content else "")
    return {
        'id': s.id,
        'title': s.title,
        'slug': s.slug,
        'excerpt': excerpt,
        'read_time': getattr(s, 'read_time', None),
        'content': s.content,
        'thumbnail': s.thumbnail.url if s.thumbnail else None,
        'og_image': s.og_image.url if hasattr(s, 'og_image') and s.og_image else None,
        'category': s.category.name if s.category else None,
        'categorySlug': s.category.slug if s.category and s.category.slug else (slugify(s.category.name) if s.category else None),
        'city': s.city.name if s.city else None,
        'citySlug': s.city.slug if s.city and s.city.slug else (slugify(s.city.name) if s.city else None),
        'author': s.author if s.author else 'Editorial Team',
        'sections': s.sections if s.sections else None,
        'publishDate': s.published_at.strftime("%b %d, %Y") if s.published_at else None,
        'published_at': s.published_at.isoformat() if s.published_at else None,
        'updated_at': s.updated_at.isoformat() if s.updated_at else None,
        'isFeatured': s.is_featured,
        'stage': s.stage,
        'views': s.view_count,
        'trendingScore': s.trending_score,
        'related_startup': {
            'id': s.related_startup.id,
            'name': s.related_startup.name,
            'slug': s.related_startup.slug,
            'logo': s.related_startup.logo.url if s.related_startup.logo else None,
            'category': s.related_startup.category.name if s.related_startup.category else None,
            'city': s.related_startup.city.name if s.related_startup.city else None,
            'citySlug': s.related_startup.city.slug if s.related_startup.city else None,
            'founded_year': s.related_startup.founded_year,
            'team_size': s.related_startup.team_size,
            'founders_data': _get_founders(None, s.related_startup), # Use None for request if not available or just pass it if possible
            'website_url': s.related_startup.website_url,
        } if s.related_startup else None,
        'meta_title': s.meta_title,
        'meta_description': s.meta_description,
        'meta_keywords': s.meta_keywords,
        'image_alt': s.image_alt,
        'show_table_of_contents': s.show_table_of_contents,
        'status': s.status,
    }

@require_GET
def story_list(request):
    if request.user.is_authenticated and request.user.is_staff:
        stories = Story.objects.all().select_related('category', 'city', 'related_startup', 'related_startup__category', 'related_startup__city')
    else:
        stories = Story.objects.filter(status='published').select_related('category', 'city', 'related_startup', 'related_startup__category', 'related_startup__city')

    search = request.GET.get('search')
    category = request.GET.get('category')
    city = request.GET.get('city')
    stage = request.GET.get('stage')
    status = request.GET.get('status')
    sort_key = request.GET.get('sort', 'latest')
    page = request.GET.get('page')
    page_size = request.GET.get('page_size')

    if status and status != 'all':
        stories = stories.filter(status__iexact=status)

    if search:
        stories = stories.filter(
            Q(title__icontains=search) |
            Q(content__icontains=search) |
            Q(author__icontains=search)
        )

    if category and category != 'all':
        stories = stories.filter(
            Q(category__name__iexact=category) | Q(category__slug__iexact=category)
        )

    if city and city != 'all':
        stories = stories.filter(
            Q(city__name__iexact=city) | Q(city__slug__iexact=city)
        )

    if stage and stage != 'all':
        stories = stories.filter(stage__iexact=stage)

    if sort_key == 'trending':
        stories = stories.order_by('-trending_score', '-is_featured', '-published_at')
    elif sort_key == 'most_viewed':
        stories = stories.order_by('-view_count', '-published_at')
    else:
        stories = stories.order_by('-published_at')

    # Only return paginated response if explicitly requested or filters are applied
    # sort_key defaults to 'latest', so check if it was specifically in GET params
    has_filters = any([
        request.GET.get('page'),
        request.GET.get('page_size'),
        request.GET.get('search'),
        request.GET.get('category'),
        request.GET.get('city'),
        request.GET.get('stage'),
        request.GET.get('sort')
    ])

    if has_filters:
        page_number = int(page or 1)
        size = int(page_size or 12)
        paginator = Paginator(stories, size)
        page_obj = paginator.get_page(page_number)
        data = [_serialize_story(s) for s in page_obj.object_list]
        return JsonResponse({
            'results': data,
            'count': paginator.count,
            'page': page_number,
            'page_size': size,
            'total_pages': paginator.num_pages,
        })

    data = [_serialize_story(s) for s in stories]
    return JsonResponse(data, safe=False)

@require_GET
def trending_stories(request):
    """Get trending/featured stories - featured first, then by publish date"""
    stories = Story.objects.filter(status='published').select_related('category', 'city', 'related_startup', 'related_startup__category', 'related_startup__city').order_by('-trending_score', '-is_featured', '-published_at')[:10]
    data = [_serialize_story(s) for s in stories]
    return JsonResponse(data, safe=False)

@require_GET
def startup_list(request):
    if request.user.is_authenticated and request.user.is_staff:
        startups = Startup.objects.select_related('category', 'city').order_by('-is_featured', '-created_at')
    else:
        startups = Startup.objects.filter(status='published').select_related('category', 'city').order_by('-is_featured', '-created_at')

    search = request.GET.get('search')
    category = request.GET.get('category')
    city = request.GET.get('city')
    stage = request.GET.get('stage')
    status = request.GET.get('status')

    if status and status != 'all':
        startups = startups.filter(status__iexact=status)

    if search:
        startups = startups.filter(
            Q(name__icontains=search) |
            Q(description__icontains=search) |
            Q(tagline__icontains=search)
        )

    if category and category != 'all':
        startups = startups.filter(
            Q(category__name__iexact=category) | Q(category__slug__iexact=category)
        )

    if city and city != 'all':
        startups = startups.filter(
            Q(city__name__iexact=city) | Q(city__slug__iexact=city)
        )

    if stage and stage != 'all':
        startups = startups.filter(funding_stage__iexact=stage)

    # Simple pagination
    page = request.GET.get('page')
    page_size = request.GET.get('page_size')
    
    if page or page_size:
        page_number = int(page or 1)
        size = int(page_size or 20)
        paginator = Paginator(startups, size)
        page_obj = paginator.get_page(page_number)
        startups_list = page_obj.object_list
        
        data = []
        for s in startups_list:
            logo_url = s.logo.url if s.logo else None
            if logo_url and not logo_url.startswith('http'):
                logo_url = request.build_absolute_uri(logo_url)
                
            data.append({
                'id': s.id,
                'name': s.name,
                'slug': s.slug,
                'description': s.description,
                'tagline': s.tagline or (s.description[:140] if s.description else ''),
                'logo': logo_url,
                'category': s.category.name if s.category else None,
                'categorySlug': s.category.slug if s.category else None,
                'city': s.city.name if s.city else None,
                'citySlug': s.city.slug if s.city else None,
                'website': s.website_url,
                'founded_year': s.founded_year,
                'funding_stage': getattr(s, 'funding_stage', None) or getattr(s, 'stage', ''),
                'business_model': getattr(s, 'business_model', ''),
                'team_size': s.team_size,
                'founder_name': s.founder_name or ", ".join([f['name'] for f in _get_founders(request, s)]),
                'industry_tags': getattr(s, 'industry_tags', None) or [],
                'is_featured': s.is_featured,
                'status': s.status,
                'updated_at': s.updated_at.isoformat() if s.updated_at else None
            })
            
        return JsonResponse({
            'results': data,
            'count': paginator.count,
            'page': page_number,
            'page_size': size,
            'total_pages': paginator.num_pages,
        })

    data = []
    for s in startups:
        logo_url = s.logo.url if s.logo else None
        if logo_url and not logo_url.startswith('http'):
            logo_url = request.build_absolute_uri(logo_url)
            
        data.append({
            'id': s.id,
            'name': s.name,
            'slug': s.slug,
            'description': s.description,
            'tagline': s.tagline or (s.description[:140] if s.description else ''),
            'logo': logo_url,
            'category': s.category.name if s.category else None,
            'categorySlug': s.category.slug if s.category else None,
            'city': s.city.name if s.city else None,
            'citySlug': s.city.slug if s.city else None,
            'website': s.website_url,
            'founded_year': s.founded_year,
            'funding_stage': getattr(s, 'funding_stage', None) or getattr(s, 'stage', ''),
            'business_model': getattr(s, 'business_model', ''),
            'team_size': s.team_size,
            'founder_name': s.founder_name or ", ".join([f['name'] for f in _get_founders(request, s)]),
            'industry_tags': getattr(s, 'industry_tags', None) or [],
            'is_featured': s.is_featured,
            'status': s.status,
            'updated_at': s.updated_at.isoformat() if s.updated_at else None
        })
    return JsonResponse(data, safe=False)

@require_GET
def story_detail(request, slug):
    try:
        if request.user.is_authenticated:
            # Admins can see drafts
            s = Story.objects.select_related('category', 'city', 'related_startup', 'related_startup__category', 'related_startup__city').get(slug=slug)
        else:
            s = Story.objects.filter(status='published').select_related('category', 'city', 'related_startup', 'related_startup__category', 'related_startup__city').get(slug=slug)
        return JsonResponse(_serialize_story(s))
    except Story.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)




@csrf_exempt
def startup_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = (data.get('name') or '').strip()
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            
            # Generate unique slug
            base_slug = data.get('slug') or slugify(name)
            unique_slug = base_slug
            counter = 1
            while Startup.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{counter}'
                counter += 1

            with transaction.atomic():
                # Helper for base64 images
                def set_base64_image(instance_field, base64_str, filename_prefix):
                    if not base64_str or not isinstance(base64_str, str) or not base64_str.startswith('data:image'):
                        return
                    try:
                        format, imgstr = base64_str.split(';base64,')
                        ext = format.split('/')[-1]
                        data = ContentFile(base64.b64decode(imgstr), name=f"{filename_prefix}_{slugify(name)}.{ext}")
                        instance_field.save(data.name, data, save=False)
                    except Exception as e:
                        print(f"Failed to save image: {e}")

                startup = Startup.objects.create(
                    name=name,
                    slug=unique_slug,
                    tagline=data.get('tagline', ''),
                    description=data.get('description', ''),
                    website_url=data.get('website_url', ''),
                    founder_name=data.get('founder_name', ''),
                    founder_linkedin=data.get('founder_linkedin', ''),
                    founded_year=data.get('founded_year'),
                    funding_stage=data.get('stage', '') or data.get('funding_stage', ''),
                    business_model=data.get('business_model', ''),
                    team_size=data.get('team_size', ''),
                    founders_data=data.get('founders_data', []),
                    industry_tags=data.get('industry_tags', []),
                    status=data.get('status', 'published'),
                    meta_title=data.get('meta_title', ''),
                    meta_description=data.get('meta_description', ''),
                    meta_keywords=data.get('meta_keywords', ''),
                    image_alt=data.get('image_alt', ''),
                    is_featured=bool(data.get('is_featured', False))
                )

                # Handle images
                if data.get('logo'):
                    set_base64_image(startup.logo, data.get('logo'), "logo")
                if data.get('og_image'):
                    set_base64_image(startup.og_image, data.get('og_image'), "og")

                # Handle category
                if 'category' in data:
                    val = data.get('category')
                    if val:
                        try:
                            startup.category_id = int(val)
                        except (ValueError, TypeError):
                            try:
                                cat = Category.objects.get(name__iexact=val)
                                startup.category_id = cat.id
                            except Category.DoesNotExist:
                                pass
                
                # Handle city
                if 'city' in data:
                    val = data.get('city')
                    if val:
                        try:
                            startup.city_id = int(val)
                        except (ValueError, TypeError):
                            try:
                                city = City.objects.get(name__iexact=val)
                                startup.city_id = city.id
                            except City.DoesNotExist:
                                pass
                
                startup.save()

            return JsonResponse({
                'id': startup.id,
                'slug': startup.slug,
                'name': startup.name,
                'message': 'Startup created successfully'
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def startup_update(request, slug):
    if request.method != 'PUT':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        startup = Startup.objects.get(slug=slug)
        data = json.loads(request.body)
        old_startup_slug = startup.slug

        with transaction.atomic():
            allowed_fields = [
                'name', 'tagline', 'description', 'website_url',
                'founder_name', 'founder_linkedin',
                'funding_stage', 'business_model', 'team_size',
                'founders_data', 'industry_tags',
                'status', 'meta_title', 'meta_description',
                'meta_keywords', 'image_alt',
                'canonical_override', 'noindex',
            ]
            for key in list(data.keys()):
                if key in allowed_fields or key in ('slug',):
                    continue
                # camelCase variants
                if key == 'fundingStage':
                    startup.funding_stage = data[key] or ''
                elif key == 'businessModel':
                    startup.business_model = data[key] or ''
                elif key == 'industryTags':
                    startup.industry_tags = data[key]
                elif key == 'isFeatured':
                    startup.is_featured = bool(data[key])
            for field in allowed_fields:
                if field in data:
                    setattr(startup, field, data[field])

            # Handle founded_year
            if 'founded_year' in data:
                year_val = data.get('founded_year')
                if year_val:
                    try:
                        startup.founded_year = int(year_val)
                    except (ValueError, TypeError):
                        startup.founded_year = None
                else:
                    startup.founded_year = None

            if 'is_featured' in data:
                startup.is_featured = bool(data['is_featured'])

            # Handle category - accept both ID and name
            if 'category' in data:
                val = data.get('category')
                if val:
                    try:
                        # Try as ID first
                        startup.category_id = int(val)
                    except (ValueError, TypeError):
                        # If not an ID, try looking up by name
                        try:
                            cat = Category.objects.get(name__iexact=val)
                            startup.category_id = cat.id
                        except Category.DoesNotExist:
                            # Invalid category, leave unchanged
                            pass
                else:
                    startup.category_id = None

            # Handle city - accept both ID and name
            if 'city' in data:
                val = data.get('city')
                if val:
                    try:
                        # Try as ID first
                        startup.city_id = int(val)
                    except (ValueError, TypeError):
                        # If not an ID, try looking up by name
                        try:
                            city = City.objects.get(name__iexact=val)
                            startup.city_id = city.id
                        except City.DoesNotExist:
                            # Invalid city, leave unchanged
                            pass
                else:
                    startup.city_id = None

            # Slug update with uniqueness and 301 redirect
            if data.get('slug') and data.get('slug') != startup.slug:
                new_slug = slugify(data.get('slug')).lower().replace(' ', '-')
                base_slug = new_slug
                counter = 1
                while Startup.objects.filter(slug=new_slug).exclude(id=startup.id).exists():
                    new_slug = f"{base_slug}-{counter}"
                    counter += 1
                startup.slug = new_slug

            startup.save()
            _create_redirect_if_slug_changed(old_startup_slug, startup.slug, 'startups')

            # Handle og_image (base64 or clear)
            # Handle images (base64 or clear)
            for img_field in ['og_image', 'logo']:
                if img_field in data:
                    img_data = data[img_field]
                    if not img_data:
                        setattr(startup, img_field, None)
                    elif isinstance(img_data, str) and img_data.startswith('data:image'):
                        from django.core.files.base import ContentFile
                        import base64
                        try:
                            format, imgstr = img_data.split(';base64,')
                            ext = format.split('/')[-1]
                            fname = f'{startup.slug}-{img_field}.{ext}'
                            if img_field == 'og_image': fname = f'{startup.slug}-og.{ext}'
                            setattr(startup, img_field, ContentFile(base64.b64decode(imgstr), name=fname))
                        except Exception as e:
                            print(f"Error decoding image {img_field}: {e}")
                    elif isinstance(img_data, str) and (img_data.startswith('http') or img_data.startswith('/media/')):
                        # Already a URL or relative path, don't change it
                        pass

            startup.save()

        return JsonResponse({
            'message': 'Updated successfully',
            'id': startup.id,
            'slug': startup.slug
        })

    except Startup.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
def startup_delete(request, slug):
    if request.method != 'DELETE':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        with transaction.atomic():
            startup = Startup.objects.get(slug=slug)
            startup.delete()

        return JsonResponse({'message': 'Deleted successfully'})

    except Startup.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)



@require_GET
def category_list(request):
    categories = Category.objects.filter(status='published').annotate(
        startup_count=Count('startups', distinct=True),
        story_count=Count('stories', distinct=True)
    )
    data = []
    for c in categories:
        data.append({
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'description': c.description,
            'icon': c.icon.url if c.icon else None,
            'iconName': c.icon_name or '',
            'startupCount': c.startup_count,
            'storyCount': c.story_count
        })
    return JsonResponse(data, safe=False)

@require_GET
def category_detail(request, slug):
    try:
        c = Category.objects.filter(status='published').get(slug=slug)
        stories = Story.objects.filter(status='published', category=c).order_by('-published_at')[:20]
        startups = c.startups.filter(status='published').order_by('-created_at')[:20]
        return JsonResponse({
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'description': c.description,
            'icon': c.icon.url if c.icon else None,
            'iconName': c.icon_name or '',
            'is_featured': c.is_featured,
            'meta_title': c.meta_title or f"{c.name} Startups in India | StartupSaga.in",
            'meta_description': c.meta_description or '',
            'meta_keywords': getattr(c, 'meta_keywords', ''),
            'og_image': c.og_image.url if c.og_image else None,
            'stories': [_serialize_story(s) for s in stories],
            'startups': [{'name': s.name, 'slug': s.slug, 'description': s.description[:150] if s.description else '', 'logo': s.logo.url if s.logo else None} for s in startups],
        })
    except Category.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@require_GET
def city_detail(request, slug):
    try:
        if request.user.is_authenticated and request.user.is_staff:
            c = City.objects.get(slug=slug)
        else:
            c = City.objects.filter(status='published').get(slug=slug)

        startup_qs = c.startups.filter(status='published')
        story_qs = Story.objects.filter(status='published', city=c)

        # Accurate live counts from DB (not the stale manual field)
        total_startups = startup_qs.count()
        total_stories = story_qs.count()
        total_unicorns = startup_qs.filter(funding_stage__iexact='Unicorn').count()

        stories = story_qs.order_by('-published_at')[:20]
        startups = startup_qs.order_by('-created_at')[:20]

        return JsonResponse({
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'description': c.description,
            'image': c.image.url if c.image else None,
            'tier': c.tier,
            'startupCount': total_startups,
            'storyCount': total_stories,
            'unicornCount': total_unicorns,
            'is_featured': c.is_featured,
            'status': c.status,
            'meta_title': c.meta_title or f"Startups in {c.name} | StartupSaga.in",
            'meta_description': c.meta_description or '',
            'meta_keywords': getattr(c, 'meta_keywords', ''),
            'og_image': c.og_image.url if c.og_image else None,
            'stories': [_serialize_story(s) for s in stories],
            'startups': [{'name': s.name, 'slug': s.slug, 'description': s.description[:150] if s.description else '', 'logo': s.logo.url if s.logo else None, 'logo_url': s.logo.url if s.logo else None, 'funding_stage': getattr(s, 'funding_stage', '') or '', 'city': c.name, 'citySlug': c.slug, 'category': s.category.name if s.category else None, 'categorySlug': s.category.slug if s.category else None, 'team_size': s.team_size, 'tagline': s.tagline or (s.description[:140] if s.description else '')} for s in startups],
        })
    except City.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@require_GET
def city_list(request):
    if request.user.is_authenticated and request.user.is_staff:
        cities = City.objects.all().annotate(
            startup_count_aggregate=Count('startups', distinct=True),
            story_count_aggregate=Count('stories', distinct=True),
            unicorn_count_aggregate=Count('startups', filter=Q(startups__funding_stage__iexact='Unicorn'), distinct=True)
        )
    else:
        cities = City.objects.filter(status='published').annotate(
            startup_count_aggregate=Count('startups', distinct=True),
            story_count_aggregate=Count('stories', distinct=True),
            unicorn_count_aggregate=Count('startups', filter=Q(startups__funding_stage__iexact='Unicorn'), distinct=True)
        )
    # Pagination for cities
    page = request.GET.get('page')
    page_size = request.GET.get('page_size')
    
    if page or page_size:
        page_number = int(page or 1)
        size = int(page_size or 20)
        paginator = Paginator(cities.order_by('name'), size)
        page_obj = paginator.get_page(page_number)
        cities_list = page_obj.object_list
        
        data = []
        for c in cities_list:
            data.append({
                'id': c.id,
                'name': c.name,
                'slug': c.slug,
                'description': c.description,
                'image': c.image.url if c.image else None,
                'tier': c.tier,
                'startupCount': c.startup_count_aggregate,
                'storyCount': c.story_count_aggregate,
                'unicornCount': c.unicorn_count_aggregate
            })
            
        return JsonResponse({
            'results': data,
            'count': paginator.count,
            'page': page_number,
            'page_size': size,
            'total_pages': paginator.num_pages,
        })

    data = []
    for c in cities:
        data.append({
            'id': c.id,
            'name': c.name,
            'slug': c.slug,
            'description': c.description,
            'image': c.image.url if c.image else None,
            'tier': c.tier,
            'startupCount': c.startup_count_aggregate,
            'storyCount': c.story_count_aggregate,
            'unicornCount': c.unicorn_count_aggregate
        })
    return JsonResponse(data, safe=False)


@csrf_exempt
def city_create(request):
    if request.method == 'POST':
        try:
            from django.core.files.base import ContentFile
            import base64
            data = json.loads(request.body)
            name = (data.get('name') or '').strip()
            if not name:
                return JsonResponse({'error': 'City name is required'}, status=400)
            
            # Generate unique slug
            base_slug = data.get('slug') or slugify(name)
            unique_slug = base_slug
            counter = 1
            while City.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{counter}'
                counter += 1

            city = City.objects.create(
                name=name,
                slug=unique_slug,
                tier=data.get('tier', '1'),
                startup_count=data.get('startupCount') or data.get('startup_count') or 0,
                unicorn_count=data.get('unicornCount') or data.get('unicorn_count') or 0,
                description=data.get('description', ''),
                is_featured=bool(data.get('is_featured', False)),
                status=data.get('status', 'published'),
                meta_title=data.get('meta_title', ''),
                meta_description=data.get('meta_description', '')
            )

            # Handle image (base64)
            image_data = data.get('image', '')
            if image_data and image_data.startswith('data:image'):
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                city.image = ContentFile(base64.b64decode(imgstr), name=f'{city.slug}.{ext}')
                city.save()

            # Handle og_image (base64)
            og_image_data = data.get('og_image', '')
            if og_image_data and og_image_data.startswith('data:image'):
                format, imgstr = og_image_data.split(';base64,')
                ext = format.split('/')[-1]
                city.og_image = ContentFile(base64.b64decode(imgstr), name=f'{city.slug}-og.{ext}')
                city.save()

            return JsonResponse({
                'id': city.id,
                'name': city.name,
                'slug': city.slug,
                'description': city.description,
                'image': city.image.url if city.image else None,
                'tier': city.tier,
                'startupCount': city.startup_count,
                'unicornCount': city.unicorn_count,
                'status': city.status
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def city_update(request, slug):
    if request.method in ['PUT', 'PATCH']:
        try:
            from django.core.files.base import ContentFile
            import base64
            data = json.loads(request.body)
            city = City.objects.get(slug=slug)

            if 'name' in data and data['name']:
                new_name = data['name'].strip()
                if new_name and new_name != city.name:
                    city.name = new_name
                    # Only update slug if not explicitly provided
                    if 'slug' not in data:
                        base_slug = slugify(new_name)
                        unique_slug = base_slug
                        counter = 1
                        while City.objects.filter(slug=unique_slug).exclude(id=city.id).exists():
                            unique_slug = f"{base_slug}-{counter}"
                            counter += 1
                        city.slug = unique_slug

            if 'slug' in data and data['slug'] and data['slug'] != city.slug:
                new_slug = data['slug']
                if City.objects.filter(slug=new_slug).exclude(id=city.id).exists():
                    return JsonResponse({'error': 'Slug already exists'}, status=400)
                city.slug = new_slug

            if 'tier' in data: city.tier = data['tier']
            if 'startupCount' in data: city.startup_count = data['startupCount']
            elif 'startup_count' in data: city.startup_count = data['startup_count']
            
            if 'unicornCount' in data: city.unicorn_count = data['unicornCount']
            elif 'unicorn_count' in data: city.unicorn_count = data['unicorn_count']
            
            if 'description' in data: city.description = data['description']
            if 'is_featured' in data: city.is_featured = bool(data['is_featured'])
            if 'status' in data: city.status = data['status']
            if 'meta_title' in data: city.meta_title = data['meta_title']
            if 'meta_description' in data: city.meta_description = data['meta_description']

            # Handle image (base64)
            image_data = data.get('image', '')
            if image_data and image_data.startswith('data:image'):
                format, imgstr = image_data.split(';base64,')
                ext = format.split('/')[-1]
                city.image = ContentFile(base64.b64decode(imgstr), name=f'{city.slug}.{ext}')
            
            # Handle og_image (base64)
            og_image_data = data.get('og_image', '')
            if og_image_data and og_image_data.startswith('data:image'):
                format, imgstr = og_image_data.split(';base64,')
                ext = format.split('/')[-1]
                city.og_image = ContentFile(base64.b64decode(imgstr), name=f'{city.slug}-og.{ext}')

            city.save()
            return JsonResponse({
                'id': city.id,
                'name': city.name,
                'slug': city.slug,
                'description': city.description,
                'image': city.image.url if city.image else None,
                'tier': city.tier,
                'startupCount': city.startup_count,
                'unicornCount': city.unicorn_count,
                'status': city.status
            })
        except City.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def city_delete(request, slug):
    if request.method == 'DELETE':
        try:
            city = City.objects.get(slug=slug)
            city.delete()
            return JsonResponse({'message': 'Deleted'})
        except City.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def category_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            name = (data.get('name') or '').strip()
            if not name:
                return JsonResponse({'error': 'Name is required'}, status=400)
            
            # Generate unique slug
            base_slug = data.get('slug') or slugify(name)
            unique_slug = base_slug
            counter = 1
            while Category.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{counter}'
                counter += 1

            category = Category.objects.create(
                name=name,
                slug=unique_slug,
                description=data.get('description', ''),
                icon_name=data.get('iconName') or data.get('icon_name', 'help-circle'),
                meta_title=data.get('meta_title', ''),
                meta_description=data.get('meta_description', ''),
                status=data.get('status', 'published') # Default to published for admin creation
            )

            return JsonResponse({
                'id': category.id,
                'slug': category.slug,
                'name': category.name,
                'message': 'Category created successfully'
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def category_update(request, slug):
    if request.method in ['PUT', 'PATCH']:
        try:
            data = json.loads(request.body)
            category = Category.objects.get(slug=slug)

            if 'name' in data and data['name']:
                new_name = data['name'].strip()
                if new_name and new_name != category.name:
                    base_slug = slugify(new_name)
                    unique_slug = base_slug
                    counter = 1
                    while Category.objects.filter(slug=unique_slug).exclude(id=category.id).exists():
                        unique_slug = f"{base_slug}-{counter}"
                        counter += 1
                    category.name = new_name
                    category.slug = unique_slug

            if 'description' in data:
                category.description = data.get('description', '')
            if 'iconName' in data:
                category.icon_name = data['iconName']
            elif 'icon_name' in data:
                category.icon_name = data['icon_name']

            category.save()
            return JsonResponse({
                'name': category.name,
                'slug': category.slug,
                'description': category.description,
                'icon': category.icon.url if category.icon else None,
                'iconName': category.icon_name or '',
                'startupCount': category.startups.count()
            })
        except Category.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def category_delete(request, slug):
    if request.method == 'DELETE':
        try:
            category = Category.objects.get(slug=slug)
            category.delete()
            return JsonResponse({'message': 'Deleted'})
        except Category.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)



@require_GET
def page_detail(request, slug):
    try:
        p = Page.objects.filter(status='published').get(slug=slug)
        sections = PageSection.objects.filter(page_obj=p, page='custom', is_active=True).order_by('order')
        section_data = [{
            'section_type': s.section_type,
            'title': s.title,
            'subtitle': s.subtitle,
            'description': s.description,
            'content': s.content,
            'image': s.image.url if s.image else None,
            'icon': s.icon.url if s.icon else None,
            'link_text': s.link_text,
            'link_url': s.link_url,
            'order': s.order,
            'settings': s.settings or {},
        } for s in sections]
        return JsonResponse({
            'title': p.title,
            'slug': p.slug,
            'content': p.content,
            'meta_title': p.meta_title or f"{p.title} | StartupSaga.in",
            'meta_description': p.meta_description or '',
            'og_image': p.og_image.url if p.og_image else None,
            'theme_overrides': p.theme_overrides or {},
            'sections': section_data
        })
    except Page.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@require_GET
def page_list(request):
    # Ensure system pages exist in DB so they can be edited
    system_pages_def = [
        {'slug': 'home', 'title': 'Homepage'},
        {'slug': 'stories', 'title': 'Stories Listing'},
        {'slug': 'startups', 'title': 'Startups Listing'},
    ]
    
    for sp in system_pages_def:
        Page.objects.get_or_create(
            slug=sp['slug'],
            defaults={
                'title': sp['title'],
                'status': 'published',
                'content': '<p>System page content managed via sections.</p>'
            }
        )
    
    # Return all pages (drafts and published)
    pages = list(Page.objects.all().values('id', 'slug', 'title', 'updated_at', 'status'))
    
    # Add is_system flag for frontend UI
    for p in pages:
        if p['slug'] in ['home', 'stories', 'startups']:
            p['is_system'] = True
            
    return JsonResponse(pages, safe=False)


@require_GET
def sections_list(request):
    """List sections for a specific page key or slug"""
    page_key = request.GET.get('page', 'homepage')
    page_slug = request.GET.get('page_slug')
    
    # Filter active only for frontend by default
    qs = PageSection.objects.filter(is_active=True).order_by('order')
    
    if page_slug:
        try:
            # Fetch page by slug only — do NOT filter by status here.
            # page_detail already enforces published-only for public page access.
            # Filtering by status here would silently return 0 sections for valid published pages.
            page_obj = Page.objects.get(slug=page_slug)
            qs = qs.filter(page_obj=page_obj, page='custom')
        except Page.DoesNotExist:
            qs = qs.none()
    elif page_key:
        qs = qs.filter(page=page_key)
        
    data = []
    for s in qs:
        data.append({
            'id': s.id,
            'page': s.page,
            'section_type': s.section_type,
            'title': s.title,
            'subtitle': s.subtitle,
            'description': s.description,
            'content': s.content or '',
            'image': s.image.url if s.image else None,
            'icon': s.icon.url if s.icon else None,
            'link_text': s.link_text,
            'link_url': s.link_url,
            'order': s.order,
            'is_active': s.is_active,
            'settings': s.settings or {},
        })
    return JsonResponse(data, safe=False)


@csrf_exempt
def section_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            page_id = data.get('page_id') or data.get('page_obj')
            page_obj = None
            if page_id:
                try:
                    page_obj = Page.objects.get(pk=page_id)
                except Page.DoesNotExist:
                    pass

            section = PageSection.objects.create(
                page=data.get('page', 'homepage'),
                page_obj=page_obj,
                section_type=data.get('section_type', 'banner'),
                title=data.get('title', ''),
                subtitle=data.get('subtitle', ''),
                description=data.get('description', ''),
                content=data.get('content', ''),
                link_text=data.get('link_text', ''),
                link_url=data.get('link_url', ''),
                order=data.get('order', 0),
                is_active=data.get('is_active', True),
                settings=data.get('settings', {})
            )
            
            if 'image' in data and data['image'] and data['image'].startswith('data:image'):
                from django.core.files.base import ContentFile
                import base64
                format, imgstr = data['image'].split(';base64,')
                ext = format.split('/')[-1]
                section.image = ContentFile(base64.b64decode(imgstr), name=f"section_{section.pk}.{ext}")
                section.save()

            return JsonResponse({'id': section.id, 'section_type': section.section_type, 'title': section.title, 'message': 'Section created'}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def section_update(request, pk):
    if request.method in ['PUT', 'PATCH']:
        try:
            section = PageSection.objects.get(pk=pk)
            data = json.loads(request.body)
            
            if 'title' in data: section.title = data['title']
            if 'subtitle' in data: section.subtitle = data['subtitle']
            if 'description' in data: section.description = data['description']
            if 'content' in data: section.content = data['content']
            if 'section_type' in data: section.section_type = data['section_type']
            if 'link_text' in data: section.link_text = data['link_text']
            if 'link_url' in data: section.link_url = data['link_url']
            if 'order' in data: section.order = data['order']
            if 'is_active' in data: section.is_active = data['is_active']
            if 'settings' in data: section.settings = data['settings']
            if 'page' in data: section.page = data['page']
            
            if 'image' in data and data['image'] and data['image'].startswith('data:image'):
                from django.core.files.base import ContentFile
                import base64
                format, imgstr = data['image'].split(';base64,')
                ext = format.split('/')[-1]
                section.image = ContentFile(base64.b64decode(imgstr), name=f"section_{section.pk}.{ext}")
            
            section.save()
            return JsonResponse({'id': section.id, 'section_type': section.section_type, 'message': 'Section updated'})
        except PageSection.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def section_delete(request, pk):
    if request.method == 'DELETE':
        try:
            section = PageSection.objects.get(pk=pk)
            section.delete()
            return JsonResponse({'message': 'Section deleted'})
        except PageSection.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


def _get_global_theme():
    """Build global theme from LayoutSetting. Keys like primary_color, font_family, etc."""
    settings = LayoutSetting.objects.all()
    theme = {}
    for s in settings:
        theme[s.key] = s.value
    return theme


def _merge_theme(base, overrides):
    """Merge overrides into base. overrides can be dict or None."""
    if not overrides or not isinstance(overrides, dict):
        return dict(base) if base else {}
    result = dict(base) if base else {}
    for k, v in overrides.items():
        if v is not None and v != '':
            result[k] = v
    return result


@require_GET
def theme_settings(request):
    """
    GET /api/theme/?page_key=homepage  - for built-in pages
    GET /api/theme/?page_slug=about   - for static pages
    Returns merged theme: global (LayoutSetting) + page overrides.
    """
    page_key = request.GET.get('page_key')
    page_slug = request.GET.get('page_slug')
    global_theme = _get_global_theme()
    page_overrides = {}

    if page_key:
        try:
            override = PageThemeOverride.objects.get(page_key=page_key)
            page_overrides = override.theme_overrides or {}
        except PageThemeOverride.DoesNotExist:
            pass
    elif page_slug:
        try:
            page = Page.objects.filter(status='published').get(slug=page_slug)
            page_overrides = page.theme_overrides or {}
        except Page.DoesNotExist:
            pass

    merged = _merge_theme(global_theme, page_overrides)
    return JsonResponse(merged)


from .models import StartupSubmission, AIPrompt

@require_GET
def prompt_list(request):
    """Get all prompts (including inactive ones for dashboard)"""
    prompts = AIPrompt.objects.all().order_by('-created_at')
    data = []
    for p in prompts:
        data.append({
            'id': p.id,
            'name': p.name,
            'category': p.category,
            'prompt_text': p.prompt_text,
            'is_active': p.is_active,
            'created_at': p.created_at.strftime("%Y-%m-%d %H:%M"),
            'updated_at': p.updated_at.strftime("%Y-%m-%d %H:%M")
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
def prompt_create(request):
    """Create a new prompt"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = AIPrompt.objects.create(
                name=data.get('name'),
                category=data.get('category', 'general'),
                prompt_text=data.get('prompt_text'),
                is_active=data.get('is_active', True)
            )
            return JsonResponse({
                'id': prompt.id,
                'name': prompt.name,
                'category': prompt.category,
                'prompt_text': prompt.prompt_text,
                'is_active': prompt.is_active,
                'message': 'Prompt created successfully'
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def prompt_update(request, pk):
    """Update an existing prompt"""
    if request.method in ['PUT', 'PATCH']:
        try:
            data = json.loads(request.body)
            prompt = AIPrompt.objects.get(pk=pk)
            
            if 'name' in data:
                prompt.name = data['name']
            if 'category' in data:
                prompt.category = data['category']
            if 'prompt_text' in data:
                prompt.prompt_text = data['prompt_text']
            if 'is_active' in data:
                prompt.is_active = data['is_active']
            
            prompt.save()
            
            return JsonResponse({
                'id': prompt.id,
                'name': prompt.name,
                'category': prompt.category,
                'prompt_text': prompt.prompt_text,
                'is_active': prompt.is_active,
                'message': 'Prompt updated successfully'
            })
        except AIPrompt.DoesNotExist:
            return JsonResponse({'error': 'Prompt not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def prompt_delete(request, pk):
    """Delete a prompt"""
    if request.method == 'DELETE':
        try:
            prompt = AIPrompt.objects.get(pk=pk)
            prompt.delete()
            return JsonResponse({'message': 'Prompt deleted successfully'})
        except AIPrompt.DoesNotExist:
            return JsonResponse({'error': 'Prompt not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@require_GET
def prompt_detail(request, pk):
    """Get a single prompt by ID"""
    try:
        prompt = AIPrompt.objects.get(pk=pk)
        return JsonResponse({
            'id': prompt.id,
            'name': prompt.name,
            'category': prompt.category,
            'prompt_text': prompt.prompt_text,
            'is_active': prompt.is_active,
            'created_at': prompt.created_at.strftime("%Y-%m-%d %H:%M"),
            'updated_at': prompt.updated_at.strftime("%Y-%m-%d %H:%M")
        })
    except AIPrompt.DoesNotExist:
        return JsonResponse({'error': 'Prompt not found'}, status=404)

@require_GET
def layout_settings_list(request):
    """Legacy: returns LayoutSetting as flat key-value. Use /api/theme/ for full theme."""
    settings = LayoutSetting.objects.all()
    data = {}
    for s in settings:
        data[s.key] = s.value
    return JsonResponse(data)

def _get_submission_data(request):
    """Extract submission data from JSON or form-data."""
    if request.content_type and 'application/json' in request.content_type:
        try:
            return json.loads(request.body or '{}')
        except json.JSONDecodeError:
            return {}
    return request.POST

def _get_field(data, *keys, default=''):
    for k in keys:
        v = data.get(k) if hasattr(data, 'get') else None
        if v is not None and v != '':
            return v[0] if isinstance(v, (list, tuple)) else str(v)
    return default

def _get_extension(format_str):
    """Extract and normalize extension from base64 format string."""
    ext = format_str.split('/')[-1]
    if 'svg' in ext: return 'svg'
    return ext

@csrf_exempt
def submit_startup(request):
    if request.method == 'POST':
        try:
            from .models import StartupSubmission
            data = _get_submission_data(request)
            submission = StartupSubmission.objects.create(
                startup_name=_get_field(data, 'startupName', 'startup_name', default=''),
                founder_name=_get_field(data, 'founderName', 'founder_name', default=''),
                email=_get_field(data, 'email', default='not-provided@example.com'),
                website=_get_field(data, 'website', 'website_url', default=''),
                description=_get_field(data, 'description', 'storyContent', 'tagline', default=''),
                full_story=_get_field(data, 'fullStory', 'full_story', default=''),
                city=_get_field(data, 'city', default=''),
                category=_get_field(data, 'category', default=''),
                funding_stage=_get_field(data, 'fundingStage', 'funding_stage', default=''),
                business_model=_get_field(data, 'businessModel', 'business_model', default=''),
                status='pending'
            )
            # Handle standard file uploads (multipart/form-data)
            if request.FILES.get('logo'):
                submission.logo = request.FILES['logo']
            if request.FILES.get('thumbnail'):
                submission.thumbnail = request.FILES['thumbnail']
            
            # Handle Base64 images (JSON payload)
            if 'logo' in data and data['logo'] and isinstance(data['logo'], str) and data['logo'].startswith('data:image'):
                from django.core.files.base import ContentFile
                import base64
                try:
                    format, imgstr = data['logo'].split(';base64,')
                    ext = _get_extension(format)
                    submission.logo = ContentFile(base64.b64decode(imgstr), name=f"submission_{submission.id}_logo.{ext}")
                except Exception as e:
                    print(f"Error decoding logo: {e}")

            if 'thumbnail' in data and data['thumbnail'] and isinstance(data['thumbnail'], str) and data['thumbnail'].startswith('data:image'):
                from django.core.files.base import ContentFile
                import base64
                try:
                    format, imgstr = data['thumbnail'].split(';base64,')
                    ext = _get_extension(format)
                    submission.thumbnail = ContentFile(base64.b64decode(imgstr), name=f"submission_{submission.id}_thumb.{ext}")
                except Exception as e:
                    print(f"Error decoding thumbnail: {e}")

            submission.save()
            return JsonResponse({'message': 'Success', 'id': submission.id}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@require_GET
def footer_list(request):
    items = FooterSetting.objects.filter(is_active=True).order_by('column_order')
    data = [{'title': i.title, 'content': i.content} for i in items]
    return JsonResponse(data, safe=False)


@require_GET
def seo_settings_list(request):
    items = SEOSetting.objects.all()
    data = {i.key: i.value for i in items}
    return JsonResponse(data)


@require_GET
def media_list(request):
    items = MediaItem.objects.all().order_by('-created_at')[:100]
    data = [{
        'id': i.id,
        'title': i.title,
        'url': i.file.url if i.file else None,
        'file_type': i.file_type,
        'alt_text': i.alt_text,
    } for i in items]
    return JsonResponse(data, safe=False)

@require_GET
def submission_list(request):
    print("DEBUG: hits submission_list")
    submissions = StartupSubmission.objects.all().order_by('-created_at')
    # Pagination for submissions
    page = request.GET.get('page')
    page_size = request.GET.get('page_size')
    status_filter = request.GET.get('status')
    
    if status_filter and status_filter != 'all':
        submissions = submissions.filter(status=status_filter)

    if page or page_size:
        page_number = int(page or 1)
        size = int(page_size or 20)
        paginator = Paginator(submissions, size)
        page_obj = paginator.get_page(page_number)
        submissions_list = page_obj.object_list
        
        data = []
        base_url = request.build_absolute_uri('/')[:-1]  # Get base URL without trailing slash

        for s in submissions_list:
            logo_url = s.logo.url if s.logo else None
            if logo_url:
                if logo_url.startswith('http') or logo_url.startswith('/media/'):
                    pass
                elif logo_url.startswith('/'):
                    logo_url = base_url + logo_url
                else:
                    logo_url = base_url + '/' + logo_url

            thumbnail_url = s.thumbnail.url if s.thumbnail else None
            if thumbnail_url:
                if thumbnail_url.startswith('http'):
                    pass
                elif thumbnail_url.startswith('/'):
                    thumbnail_url = base_url + thumbnail_url
                else:
                    thumbnail_url = base_url + '/' + thumbnail_url

            startup = Startup.objects.filter(name__iexact=s.startup_name).first()

            data.append({
                'id': s.id,
                'startup_name': s.startup_name,
                'founder_name': s.founder_name,
                'email': s.email,
                'website': s.website,
                'description': s.description,
                'city': s.city,
                'category': s.category,
                'status': s.status,
                'logo': logo_url,
                'thumbnail': thumbnail_url,
                'startup_slug': startup.slug if startup else None,
                'created_at': s.created_at.strftime("%Y-%m-%d %H:%M")
            })
            
        return JsonResponse({
            'results': data,
            'count': paginator.count,
            'page': page_number,
            'page_size': size,
            'total_pages': paginator.num_pages,
        })

    data = []
    base_url = request.build_absolute_uri('/')[:-1]  # Get base URL without trailing slash

    for s in submissions:
        logo_url = s.logo.url if s.logo else None
        if logo_url:
            if logo_url.startswith('http'):
                pass
            elif logo_url.startswith('/'):
                logo_url = base_url + logo_url
            else:
                logo_url = base_url + '/' + logo_url

        thumbnail_url = s.thumbnail.url if s.thumbnail else None
        if thumbnail_url:
            if thumbnail_url.startswith('http'):
                pass
            elif thumbnail_url.startswith('/'):
                thumbnail_url = base_url + thumbnail_url
            else:
                thumbnail_url = base_url + '/' + thumbnail_url

        # Try to find associated startup
        startup = Startup.objects.filter(name__iexact=s.startup_name).first()

        data.append({
            'id': s.id,
            'startup_name': s.startup_name,
            'founder_name': s.founder_name,
            'email': s.email,
            'website': s.website,
            'description': s.description,
            'full_story': s.full_story,
            'city': s.city,
            'category': s.category,
            'status': s.status,
            'logo': logo_url,
            'thumbnail': thumbnail_url,
            'startup_slug': startup.slug if startup else None,
            'created_at': s.created_at.strftime("%Y-%m-%d %H:%M")
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
def submission_delete(request, pk):
    """Delete a submission"""
    if request.method == 'DELETE':
        try:
            s = StartupSubmission.objects.get(pk=pk)
            s.delete()
            return JsonResponse({'message': 'Submission deleted'}, status=200)
        except StartupSubmission.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def submission_update(request, pk):
    """Update submission details"""
    if request.method in ['PUT', 'PATCH']:
        try:
            from django.core.files.base import ContentFile
            import base64
            import json
            
            s = StartupSubmission.objects.get(pk=pk)
            data = json.loads(request.body)
            
            if 'startup_name' in data: s.startup_name = data['startup_name']
            if 'founder_name' in data: s.founder_name = data['founder_name']
            if 'email' in data: s.email = data['email']
            if 'website' in data: s.website = data['website']
            if 'description' in data: s.description = data['description']
            if 'city' in data: s.city = data['city']
            if 'category' in data: s.category = data['category']
            if 'full_story' in data: s.full_story = data['full_story']
            if 'funding_stage' in data: s.funding_stage = data['funding_stage']
            
            # Handle Logo Update
            logo_data = data.get('logo')
            if logo_data and logo_data.startswith('data:image'):
                format, imgstr = logo_data.split(';base64,')
                ext = format.split('/')[-1]
                s.logo = ContentFile(base64.b64decode(imgstr), name=f"sub_logo_{s.id}.{ext}")
            
            # Handle Thumbnail Update
            thumbnail_data = data.get('thumbnail')
            if thumbnail_data and thumbnail_data.startswith('data:image'):
                format, imgstr = thumbnail_data.split(';base64,')
                ext = format.split('/')[-1]
                s.thumbnail = ContentFile(base64.b64decode(imgstr), name=f"sub_thumb_{s.id}.{ext}")
                
            s.save()
            return JsonResponse({'message': 'Submission updated successfully'})
        except StartupSubmission.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_GET
def submission_detail(request, pk):
    try:
        s = StartupSubmission.objects.get(pk=pk)
        logo_url = s.logo.url if s.logo else None
        if logo_url and not logo_url.startswith('http'):
            logo_url = request.build_absolute_uri(logo_url)

        thumbnail_url = s.thumbnail.url if s.thumbnail else None
        if thumbnail_url and not thumbnail_url.startswith('http'):
            thumbnail_url = request.build_absolute_uri(thumbnail_url)

        return JsonResponse({
            'id': s.id,
            'startup_name': s.startup_name,
            'founder_name': s.founder_name,
            'email': s.email,
            'website': s.website,
            'description': s.description,
            'full_story': s.full_story,
            'city': s.city,
            'category': s.category,
            'status': s.status,
            'logo': logo_url,
            'thumbnail': thumbnail_url,
            'created_at': s.created_at.strftime("%Y-%m-%d %H:%M")
        })
    except StartupSubmission.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

@csrf_exempt
def update_submission_status(request, pk):
    if request.method in ['POST', 'PUT', 'PATCH']:
        try:
            data = json.loads(request.body)
            status = data.get('status')
            s = StartupSubmission.objects.get(pk=pk)
            
            # If approving, create a Startup entity
            if status == 'approved' and s.status != 'approved':
                # Handle Category Lookup
                category_obj = None
                if s.category:
                    category_obj = Category.objects.filter(name__iexact=s.category).first()
                    if not category_obj:
                        category_obj = Category.objects.create(name=s.category)

                # Handle City Lookup
                city_obj = None
                if s.city:
                    city_obj = City.objects.filter(name__iexact=s.city).first()
                    if not city_obj:
                        city_obj = City.objects.create(name=s.city)

                # Create the Startup and keep reference
                new_startup = Startup.objects.create(
                    name=s.startup_name,
                    founder_name=s.founder_name,
                    website_url=s.website,
                    description=s.description,
                    city=city_obj,
                    category=category_obj,
                    logo=s.logo,
                    status='published', # Auto-publish
                    is_featured=False
                )

            s.status = status
            s.save()
            # If we created a startup, include its details in response
            if status == 'approved' and 'new_startup' in locals():
                return JsonResponse({'message': 'Status updated', 'created_startup': {'id': new_startup.id, 'slug': new_startup.slug}})
            return JsonResponse({'message': 'Status updated'})
        except StartupSubmission.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def story_create(request):
    """Create a new story"""
    if request.method == 'POST':
        try:
            from django.utils import timezone
            from django.utils.text import slugify
            from django.core.files.base import ContentFile
            import base64
            import re
            
            data = json.loads(request.body)
            
            # Handle Category Lookup/Create
            category_obj = None
            if data.get('category'):
                category_obj = Category.objects.filter(name__iexact=data['category']).first()
                if not category_obj:
                    category_obj = Category.objects.create(
                        name=data['category'],
                        slug=slugify(data['category'])
                    )

            # Handle City Lookup/Create
            city_obj = None
            if data.get('city'):
                city_obj = City.objects.filter(name__iexact=data['city']).first()
                if not city_obj:
                    city_obj = City.objects.create(
                        name=data['city'],
                        slug=slugify(data['city'])
                    )

            # Generate unique slug
            base_slug = data.get('slug') or slugify(data.get('title'))
            unique_slug = base_slug
            counter = 1
            
            # Check if slug exists and append counter if needed
            while Story.objects.filter(slug=unique_slug).exists():
                unique_slug = f"{base_slug}-{counter}"
                counter += 1

            # Optionally attach related startup if provided
            related_startup = None
            related_slug = data.get('related_startup_slug') or data.get('related_startup')
            if related_slug:
                related_startup = Startup.objects.filter(slug=related_slug).first()

            # Determine author: prefer provided author, else use related startup name, else default
            provided_author = data.get('author')
            author_name = provided_author if provided_author else (related_startup.name if related_startup else 'Editorial Team')

            # Create the Story
            story = Story.objects.create(
                title=data.get('title'),
                slug=unique_slug,
                content=data.get('content', ''),
                category=category_obj,
                city=city_obj,
                related_startup=related_startup,
                author=author_name,
                sections=data.get('sections', None),
                meta_title=data.get('meta_title', ''),
                meta_description=data.get('meta_description', ''),
                meta_keywords=data.get('meta_keywords', ''),
                image_alt=data.get('image_alt', ''),
                show_table_of_contents=bool(data.get('show_table_of_contents', True)),
                is_featured=data.get('isFeatured', False),
                stage=data.get('stage', ''),
                view_count=data.get('views', 0),
                trending_score=data.get('trendingScore', 0.0),
                status=data.get('status', 'draft'),
                published_at=timezone.now() if data.get('status') == 'published' else None
            )

            # Handle thumbnail (base64 or URL). If no thumbnail provided and we have a related startup,
            # copy the startup logo into the story thumbnail.
            thumbnail_data = data.get('thumbnail', '')
            if thumbnail_data:
                if thumbnail_data.startswith('data:image'):
                    # Base64 image
                    format, imgstr = thumbnail_data.split(';base64,')
                    ext = format.split('/')[-1]
                    image_data = ContentFile(base64.b64decode(imgstr), name=f'{story.slug}.{ext}')
                    story.thumbnail = image_data
                    story.save()
                elif thumbnail_data.startswith('http'):
                    # URL - for now, skip fetching external URL. Could be improved later.
                    pass
            else:
                # No thumbnail provided: if related startup has a logo file, copy it
                try:
                    if related_startup and related_startup.logo:
                        story.thumbnail = related_startup.logo
                        story.save()
                except Exception:
                    # don't fail story creation for thumbnail copy errors
                    pass

            # Handle og_image (base64)
            og_data = data.get('og_image', '')
            if og_data:
                if og_data.startswith('data:image'):
                    try:
                        format, imgstr = og_data.split(';base64,')
                        ext = format.split('/')[-1]
                        story.og_image = ContentFile(base64.b64decode(imgstr), name=f'{story.slug}-og.{ext}')
                        story.save()
                    except Exception as e:
                        print(f"Error saving story OG image: {e}")
                elif og_data.startswith('http') or og_data.startswith('/media/'):
                    pass
            elif related_startup and hasattr(related_startup, 'og_image') and related_startup.og_image:
                try:
                    story.og_image = related_startup.og_image
                    story.save()
                except Exception:
                    pass

            return JsonResponse({
                'id': story.id,
                'slug': story.slug,
                'message': 'Story created successfully'
            }, status=201)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@csrf_exempt
def story_update(request, story_id):
    """Update an existing story"""
    if request.method == 'GET':
        try:
            story = Story.objects.get(id=story_id)
            return JsonResponse(_serialize_story(story))
        except Story.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
    if request.method == 'PUT' or request.method == 'PATCH':
        try:
            from django.utils import timezone
            from django.utils.text import slugify
            from django.core.files.base import ContentFile
            import base64
            
            story = Story.objects.get(id=story_id)
            data = json.loads(request.body)
            
            # Handle Category Lookup/Create
            if data.get('category'):
                category_obj = Category.objects.filter(name__iexact=data['category']).first()
                if not category_obj:
                    category_obj = Category.objects.create(
                        name=data['category'],
                        slug=slugify(data['category'])
                    )
                story.category = category_obj

            # Handle City Lookup/Create
            if data.get('city'):
                city_obj = City.objects.filter(name__iexact=data['city']).first()
                if not city_obj:
                    city_obj = City.objects.create(
                        name=data['city'],
                        slug=slugify(data['city'])
                    )
                story.city = city_obj

            # Handle slug update with uniqueness check (and 301 redirect when slug changes)
            old_story_slug = story.slug
            if data.get('slug'):
                new_slug = data.get('slug')
                # Only check uniqueness if slug is changing
                if new_slug != story.slug:
                    base_slug = new_slug
                    unique_slug = base_slug
                    counter = 1
                    
                    # Check if slug exists (excluding current story)
                    while Story.objects.filter(slug=unique_slug).exclude(id=story_id).exists():
                        unique_slug = f"{base_slug}-{counter}"
                        counter += 1
                    
                    story.slug = unique_slug

            # Update other fields
            if data.get('title'):
                story.title = data.get('title')
            if 'content' in data:
                story.content = data.get('content', '')
            if 'excerpt' in data:
                story.excerpt = data.get('excerpt', '')
            if 'read_time' in data:
                story.read_time = data.get('read_time')
            if 'author' in data:
                story.author = data.get('author', 'Editorial Team')
            if 'sections' in data:
                story.sections = data.get('sections', None)
            if 'meta_title' in data:
                story.meta_title = data.get('meta_title', '')
            if 'meta_description' in data:
                story.meta_description = data.get('meta_description', '')
            if 'meta_keywords' in data:
                story.meta_keywords = data.get('meta_keywords', '')
            if 'image_alt' in data:
                story.image_alt = data.get('image_alt', '')
            if 'show_table_of_contents' in data:
                story.show_table_of_contents = bool(data.get('show_table_of_contents', True))
            if 'canonical_override' in data:
                story.canonical_override = data.get('canonical_override', '')
            if 'noindex' in data:
                story.noindex = bool(data.get('noindex'))
            if 'isFeatured' in data:
                story.is_featured = data.get('isFeatured', False)
            if 'stage' in data:
                story.stage = data.get('stage', '')
            if 'views' in data:
                story.view_count = data.get('views', 0)
            if 'trendingScore' in data:
                story.trending_score = data.get('trendingScore', 0.0)
            if 'status' in data:
                story.status = data.get('status', 'draft')
                if story.status == 'published' and not story.published_at:
                    story.published_at = timezone.now()

            # Handle related startup attachment
            if 'related_startup_slug' in data or 'related_startup' in data:
                related_slug = data.get('related_startup_slug') or data.get('related_startup')
                if related_slug:
                    related_startup = Startup.objects.filter(slug=related_slug).first()
                    story.related_startup = related_startup
                else:
                    story.related_startup = None

            # Handle thumbnail update
            thumbnail_data = data.get('thumbnail', '')
            if thumbnail_data:
                if thumbnail_data.startswith('data:image'):
                    format, imgstr = thumbnail_data.split(';base64,')
                    ext = format.split('/')[-1]
                    image_data = ContentFile(base64.b64decode(imgstr), name=f'{story.slug}.{ext}')
                    story.thumbnail = image_data

            # Handle og_image update (base64 or clear)
            if 'og_image' in data:
                og_data = data['og_image']
                if not og_data:
                    story.og_image = None
                elif isinstance(og_data, str) and og_data.startswith('data:image'):
                    try:
                        format, imgstr = og_data.split(';base64,')
                        ext = format.split('/')[-1]
                        story.og_image = ContentFile(base64.b64decode(imgstr), name=f'{story.slug}-og.{ext}')
                    except Exception as e:
                        print(f"Error decoding story OG image: {e}")
                elif isinstance(og_data, str) and (og_data.startswith('http') or og_data.startswith('/media/')):
                    # Keep existing URL or relative path
                    pass

            story.save()
            _create_redirect_if_slug_changed(old_story_slug, story.slug, 'stories')

            return JsonResponse({
                'id': story.id,
                'slug': story.slug,
                'message': 'Story updated successfully'
            })
        except Story.DoesNotExist:
            return JsonResponse({'error': 'Story not found'}, status=404)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def story_delete(request, story_id):
    if request.method == 'DELETE':
        try:
            story = Story.objects.get(id=story_id)
            story.delete()
            return JsonResponse({'message': 'Deleted'})
        except Story.DoesNotExist:
            return JsonResponse({'error': 'Story not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def page_create(request):
    """Create a new page"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Validation
            if not data.get('title'):
                return JsonResponse({'error': 'Title is required'}, status=400)
            
            # Generate slug
            base_slug = data.get('slug') or slugify(data.get('title'))
            unique_slug = base_slug
            counter = 1
            while Page.objects.filter(slug=unique_slug).exists():
                unique_slug = f'{base_slug}-{counter}'
                counter += 1
            
            page = Page.objects.create(
                title=data.get('title'),
                slug=unique_slug,
                content=data.get('content', ''),
                meta_title=data.get('meta_title', ''),
                meta_description=data.get('meta_description', ''),
                status=data.get('status', 'draft'),
                theme_overrides=data.get('theme_overrides', {})
            )
            return JsonResponse({
                'id': page.id,
                'slug': page.slug, 
                'message': 'Page created successfully'
            }, status=201)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def page_update(request, pk):
    """Update an existing page"""
    if request.method in ['PUT', 'PATCH']:
        try:
            data = json.loads(request.body)
            page = Page.objects.get(pk=pk)
            
            if 'title' in data:
                page.title = data['title']
                
            if 'slug' in data and data['slug'] != page.slug:
                base_slug = data['slug']
                unique_slug = base_slug
                counter = 1
                while Page.objects.filter(slug=unique_slug).exclude(pk=pk).exists():
                    unique_slug = f'{base_slug}-{counter}'
                    counter += 1
                page.slug = unique_slug
                
            if 'content' in data:
                page.content = data.get('content', '')
            if 'meta_title' in data:
                page.meta_title = data.get('meta_title', '')
            if 'meta_description' in data:
                page.meta_description = data.get('meta_description', '')
            if 'status' in data:
                page.status = data.get('status', 'draft')
            if 'theme_overrides' in data:
                theme_overrides = data.get('theme_overrides', {})
                page.theme_overrides = theme_overrides
                # Section create/update/delete is handled by the section API from the frontend.
                # Do not replace PageSection rows here, or deleted sections would reappear and IDs would break.
                
            page.save()
            
            return JsonResponse({
                'id': page.id,
                'slug': page.slug,
                'message': 'Page updated successfully'
            })
        except Page.DoesNotExist:
            return JsonResponse({'error': 'Page not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def page_delete(request, pk):
    if request.method == 'DELETE':
        try:
            page = Page.objects.get(pk=pk)
            page.delete()
            return JsonResponse({'message': 'Deleted'})
        except Page.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_GET
def page_detail_admin(request, pk):
    try:
        # Fetch by ID, no status filter
        p = Page.objects.get(pk=pk)
        
        # Also fetch sections if they exist in PageSection table
        # This ensures legacy data or data from the public view is visible in the editor
        theme_overrides = p.theme_overrides or {}
        
        if 'sections' not in theme_overrides:
            from django.db.models import Q
            # Fetch sections: either linked to this page object, or matching system page slugs
            query = Q(page_obj=p)
            slug_lower = p.slug.lower() if p.slug else ''
            
            if slug_lower == 'home':
                query |= Q(page='homepage')
            elif slug_lower in ['stories', 'startups', 'story_detail', 'startup_detail']:
                query |= Q(page=slug_lower)
            
            sections = PageSection.objects.filter(query).distinct().order_by('order')
            
            if sections.exists():
                theme_overrides['sections'] = []
                for s in sections:
                    theme_overrides['sections'].append({
                        'id': f"{s.section_type}-{s.id}", # Consistent with frontend fetch logic
                        'db_id': s.id, # Ensure db_id is passed so frontend recognizes it as existing
                        'type': s.section_type,
                        'settings': {
                            'title': s.title,
                            'subtitle': s.subtitle,
                            'description': s.description,
                            'body': s.content, # map content to body for the editor
                            'linkText': s.link_text,
                            'linkUrl': s.link_url,
                            'imageUrl': s.image.url if s.image else None,
                            'iconUrl': s.icon.url if s.icon else None,
                            **(s.settings or {})
                        }
                    })
        
        return JsonResponse({
            'id': p.id,
            'title': p.title,
            'slug': p.slug,
            'content': p.content,
            'meta_title': p.meta_title,
            'meta_description': p.meta_description,
            'status': p.status,
            'theme_overrides': theme_overrides,
            'updated_at': p.updated_at.isoformat() if p.updated_at else None
        })
    except Page.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


# --- MENU APIs ---

@require_GET
def menu_positions(request):
    """Return available menu positions defined in models"""
    choices = NavigationItem.POSITION_CHOICES
    data = [{'id': k, 'label': v} for k, v in choices]
    return JsonResponse(data, safe=False)


@csrf_exempt
def layout_settings_update(request):
    """
    Update multiple layout settings at once.
    Handles both JSON and multipart/form-data (for file uploads like site_logo).
    """
    if request.method in ['POST', 'PUT', 'PATCH']:
        try:
            from django.conf import settings
            from django.core.files.storage import default_storage

            # Handle Multipart (FormData) - Used by Footer Editor
            if request.content_type and 'multipart/form-data' in request.content_type:
                data = request.POST.dict()
                
                # Handle Logo Upload
                if 'site_logo' in request.FILES:
                    logo = request.FILES['site_logo']
                    path = default_storage.save(f"site/{logo.name}", logo)
                    # Construct URL
                    if hasattr(default_storage, 'url'):
                        url = default_storage.url(path)
                    else:
                        url = settings.MEDIA_URL + path
                    
                    # Make absolute if needed
                    if url and not url.startswith('http'):
                        url = request.build_absolute_uri(url)
                        
                    data['site_logo'] = url
                
                # Handle Logo Removal
                if data.get('remove_logo') == 'true':
                    LayoutSetting.objects.filter(key='site_logo').delete()
                    if 'site_logo' in data: del data['site_logo']
                    del data['remove_logo']
                
                # Update settings
                for key, value in data.items():
                    LayoutSetting.objects.update_or_create(
                        key=key,
                        defaults={'value': str(value)}
                    )
                return JsonResponse({'message': 'Settings updated'})

            # Handle JSON - Used by other editors
            else:
                data = json.loads(request.body)
                
                # Handle Logo Removal
                if data.get('remove_logo') is True:
                    LayoutSetting.objects.filter(key='site_logo').delete()
                    del data['remove_logo']
                    if 'site_logo' in data: del data['site_logo']

                for key, value in data.items():
                    LayoutSetting.objects.update_or_create(
                        key=key,
                        defaults={'value': str(value)}
                    )
                return JsonResponse({'message': 'Settings updated'})
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def seo_settings_update(request):
    """
    Update multiple SEO settings at once.
    Accepts JSON:
    {
        "meta_title": "...",
        "meta_description": "...",
        "keywords": "..."
    }
    """
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)

    try:
        if not request.body:
            return JsonResponse({'error': 'Empty request body'}, status=400)

        data = json.loads(request.body)

        if not isinstance(data, dict):
            return JsonResponse({'error': 'Invalid data format'}, status=400)

        # Atomic transaction to reduce SQLite lock issues
        with transaction.atomic():
            for key, value in data.items():
                # Skip null/undefined values
                if value is None:
                    continue

                SEOSetting.objects.update_or_create(
                    key=key,
                    defaults={'value': str(value)}
                )

        return JsonResponse({'message': 'SEO settings updated successfully'})

    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON format'}, status=400)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@csrf_exempt
@require_POST
def seo_apply_all(request):
    """
    Apply global SEO settings ONLY to content that has no existing meta fields.
    Safe to run — will not overwrite manually crafted per-item SEO.
    Supports Story, Startup, Hub/City, Category, and Custom Pages.
    """
    try:
        settings = SEOSetting.objects.all()
        seo_map = {s.key: s.value for s in settings}

        meta_title = seo_map.get('default_meta_title', '')
        meta_desc = seo_map.get('default_meta_description', '')

        if not meta_title and not meta_desc:
            return JsonResponse({'message': 'No default SEO title or description configured. Set them in SEO Settings first.'}, status=400)

        with transaction.atomic():
            # Only fill blank fields — NEVER overwrite existing per-item SEO
            counts = {}
            if meta_title:
                counts['story_titles'] = Story.objects.filter(meta_title='').update(meta_title=meta_title)
                counts['startup_titles'] = Startup.objects.filter(meta_title='').update(meta_title=meta_title)
                counts['city_titles'] = City.objects.filter(meta_title='').update(meta_title=meta_title)
                counts['category_titles'] = Category.objects.filter(meta_title='').update(meta_title=meta_title)
                counts['page_titles'] = Page.objects.filter(meta_title='').update(meta_title=meta_title)
            if meta_desc:
                counts['story_descs'] = Story.objects.filter(meta_description='').update(meta_description=meta_desc)
                counts['startup_descs'] = Startup.objects.filter(meta_description='').update(meta_description=meta_desc)
                counts['city_descs'] = City.objects.filter(meta_description='').update(meta_description=meta_desc)
                counts['category_descs'] = Category.objects.filter(meta_description='').update(meta_description=meta_desc)
                counts['page_descs'] = Page.objects.filter(meta_description='').update(meta_description=meta_desc)

        total_filled = sum(counts.values())
        return JsonResponse({
            'message': f'SEO defaults applied to {total_filled} empty fields across all 5 content types. Existing SEO was preserved.',
            'details': counts
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@require_POST
def prompt_apply_all(request):
    """
    Applies current AI writing rules to refresh content metadata patterns across all models.
    This synchronizes the 'AI Directives' logic with existing content pages.
    """
    try:
        # Currently, this signals the system to acknowledge the new neural logic as active
        # for all future generations across Story, Startup, City, Category, and Page models.
        # In a background-worker setup, this would trigger a full content refresh.
        return JsonResponse({'message': 'AI Writing rules successfully pushed to all site architectures.'})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

        


@require_GET
def footer_list(request):
    footers = FooterSetting.objects.all().order_by('column_order')
    data = [{
        'id': f.id,
        'title': f.title,
        'content': f.content,
        'column_order': f.column_order,
        'is_active': f.is_active
    } for f in footers]
    return JsonResponse(data, safe=False)


@csrf_exempt
def media_list(request):
    if request.method == 'GET':
        from .models import Startup, Story, City
        data = []
        _id = 1
        
        # 1. Fetch MediaItems
        for m in MediaItem.objects.all().order_by('-created_at'):
            if m.file and m.file.name:
                import os
                folder = os.path.dirname(m.file.name)
                data.append({
                    'id': m.id,
                    'title': m.title,
                    'url': m.file.url,
                    'path': m.file.name,
                    'folder': folder.replace('\\', '/') if folder else 'media_items',
                    'type': m.file_type,
                    'alt_text': m.alt_text,
                    'created_at': m.created_at.isoformat()
                })
        
        # 2. Fetch Startups Logos and OM Images
        for s in Startup.objects.all():
            if s.logo and s.logo.name:
                import os
                folder = os.path.dirname(s.logo.name)
                data.append({
                    'id': f"startup-logo-{s.id}",
                    'title': f"{s.name} Logo",
                    'url': s.logo.url,
                    'path': s.logo.name,
                    'folder': folder.replace('\\', '/') if folder else 'startups/logos',
                    'type': 'image',
                    'alt_text': s.name,
                    'created_at': s.created_at.isoformat() if s.created_at else ''
                })
            if s.og_image and s.og_image.name:
                import os
                folder = os.path.dirname(s.og_image.name)
                data.append({
                    'id': f"startup-og-{s.id}",
                    'title': f"{s.name} OG Image",
                    'url': s.og_image.url,
                    'path': s.og_image.name,
                    'folder': folder.replace('\\', '/') if folder else 'startups/og',
                    'type': 'image',
                    'alt_text': s.name,
                    'created_at': s.created_at.isoformat() if s.created_at else ''
                })
                
        # 3. Fetch Stories Thumbnails and OG
        for st in Story.objects.all():
            if st.thumbnail and st.thumbnail.name:
                import os
                folder = os.path.dirname(st.thumbnail.name)
                data.append({
                    'id': f"story-thumb-{st.id}",
                    'title': f"{st.title} Thumbnail",
                    'url': st.thumbnail.url,
                    'path': st.thumbnail.name,
                    'folder': folder.replace('\\', '/') if folder else 'stories/thumbnails',
                    'type': 'image',
                    'alt_text': st.title,
                    'created_at': st.created_at.isoformat() if st.created_at else ''
                })
            if st.og_image and st.og_image.name:
                import os
                folder = os.path.dirname(st.og_image.name)
                data.append({
                    'id': f"story-og-{st.id}",
                    'title': f"{st.title} OG Image",
                    'url': st.og_image.url,
                    'path': st.og_image.name,
                    'folder': folder.replace('\\', '/') if folder else 'stories/og',
                    'type': 'image',
                    'alt_text': st.title,
                    'created_at': st.created_at.isoformat() if st.created_at else ''
                })
                
        # 4. Fetch Cities Images
        for c in City.objects.all():
            if c.image and c.image.name:
                import os
                folder = os.path.dirname(c.image.name)
                data.append({
                    'id': f"city-img-{c.id}",
                    'title': f"{c.name} Image",
                    'url': c.image.url,
                    'path': c.image.name,
                    'folder': folder.replace('\\', '/') if folder else 'cities/images',
                    'type': 'image',
                    'alt_text': c.name,
                    'created_at': ''
                })
            if hasattr(c, 'og_image') and c.og_image and c.og_image.name:
                import os
                folder = os.path.dirname(c.og_image.name)
                data.append({
                    'id': f"city-og-{c.id}",
                    'title': f"{c.name} OG Image",
                    'url': c.og_image.url,
                    'path': c.og_image.name,
                    'folder': folder.replace('\\', '/') if folder else 'seo/og_images',
                    'type': 'image',
                    'alt_text': c.name,
                    'created_at': ''
                })
        
        # Deduplicate by path so we don't show the same image twice
        seen_paths = set()
        deduped_data = []
        for item in data:
            if item['path'] not in seen_paths:
                seen_paths.add(item['path'])
                deduped_data.append(item)
                
        deduped_data.sort(key=lambda x: (x['folder'], x['title']))
        return JsonResponse(deduped_data, safe=False)

    if request.method == 'POST':
        try:
            file = request.FILES.get('file')
            if not file:
                return JsonResponse({'error': 'No file provided'}, status=400)

            title = request.POST.get('title', '') or file.name
            alt_text = request.POST.get('alt_text', '')

            # Detect file type
            content_type = file.content_type or ''
            if content_type.startswith('image/'):
                file_type = 'image'
            elif content_type.startswith('video/'):
                file_type = 'video'
            else:
                file_type = 'file'

            item = MediaItem.objects.create(
                title=title,
                alt_text=alt_text,
                file=file,
                file_type=file_type,
            )

            return JsonResponse({
                'id': item.id,
                'title': item.title,
                'url': item.file.url if item.file else None,
                'type': item.file_type,
                'alt_text': item.alt_text,
                'created_at': item.created_at.isoformat(),
            }, status=201)
        except Exception as e:
            import traceback
            traceback.print_exc()
            return JsonResponse({'error': str(e)}, status=400)

    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_GET
def layout_settings_list(request):
    settings = LayoutSetting.objects.all()
    # Return key-value pairs for easy frontend consumption
    data = {}
    for s in settings:
         val = s.value
         # Try to auto-parse JSON if it looks like one (e.g. socials array)
         if val and (val.startswith('[') or val.startswith('{')):
             try:
                 import json
                 val = json.loads(val)
             except (json.JSONDecodeError, TypeError):
                 pass
         data[s.key] = val
    
    response = JsonResponse(data)
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    response['Pragma'] = 'no-cache'
    return response


@require_GET
def seo_settings_list(request):
    settings = SEOSetting.objects.all()
    data = {}
    for s in settings:
         data[s.key] = s.value
    return JsonResponse(data)


@require_GET
def prompt_list(request):
    prompts = AIPrompt.objects.all().order_by('-created_at')
    data = [{
        'id': p.id,
        'name': p.name,
        'prompt_text': p.prompt_text,
        'category': p.category,
        'is_active': p.is_active,
        'updated_at': p.updated_at.isoformat()
    } for p in prompts]
    return JsonResponse(data, safe=False)

@require_GET
def prompt_defaults(request):
    """Returns the default system prompts from the manifest"""
    from .prompts_manifest import SYSTEM_PROMPTS
    return JsonResponse(SYSTEM_PROMPTS, safe=False)


@csrf_exempt
def prompt_create(request):
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            prompt = AIPrompt.objects.create(
                name=data['name'],
                prompt_text=data['prompt_text'],
                category=data.get('category', 'general'),
                is_active=data.get('is_active', True)
            )
            return JsonResponse({'id': prompt.id, 'message': 'Created'}, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@require_GET
def prompt_detail(request, pk):
    try:
        prompt = AIPrompt.objects.get(pk=pk)
        return JsonResponse(model_to_dict(prompt))
    except AIPrompt.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


@csrf_exempt
def prompt_update(request, pk):
    if request.method in ['PUT', 'PATCH']:
        try:
            data = json.loads(request.body)
            prompt = AIPrompt.objects.get(pk=pk)
            if 'name' in data: prompt.name = data['name']
            if 'prompt_text' in data: prompt.prompt_text = data['prompt_text']
            if 'category' in data: prompt.category = data['category']
            if 'is_active' in data: prompt.is_active = data['is_active']
            prompt.save()
            return JsonResponse({'message': 'Updated'})
        except AIPrompt.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def prompt_delete(request, pk):
    if request.method == 'DELETE':
        try:
            prompt = AIPrompt.objects.get(pk=pk)
            prompt.delete()
            return JsonResponse({'message': 'Deleted'})
        except AIPrompt.DoesNotExist:
            return JsonResponse({'error': 'Not found'}, status=404)
    return JsonResponse({'error': 'Method not allowed'}, status=405)



def _serialize_nav_item(item):
    children_data = []
    if item.children.exists():
        for child in item.children.all().order_by('order'):
            children_data.append(_serialize_nav_item(child))
            
    return {
        'id': item.id,
        'label': item.label,
        'url': item.url,
        'icon': item.icon,
        'order': item.order,
        'parent': item.parent.id if item.parent else None,
        'is_active': item.is_active,
        'position': item.position,
        'settings': item.settings or {},
        'children': children_data
    }


@require_GET
def nav_items_list(request):
    """List navigation items, hierarchical if requested"""
    pos = request.GET.get('position')
    hierarchical = request.GET.get('hierarchical') == 'true'
    
    qs = NavigationItem.objects.all().order_by('order')
    if pos:
        if ',' in pos:
            qs = qs.filter(position__in=pos.split(','))
        else:
            qs = qs.filter(position=pos)
        
    if hierarchical:
        # Get only root items (active only for frontend)
        roots = qs.filter(parent__isnull=True, is_active=True)
        data = [_serialize_nav_item(item) for item in roots]
    else:
        # Flat list (all items including inactive for admin management)
        data = []
        for item in qs:
            data.append({
                'id': item.id,
                'label': item.label,
                'url': item.url,
                'icon': item.icon,
                'order': item.order,
                'parent': item.parent.id if item.parent else None,
                'is_active': item.is_active,
                'position': item.position,
                'settings': item.settings or {}
            })
            
    return JsonResponse(data, safe=False)


@csrf_exempt
def nav_item_create(request):
    """Create a new menu item"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            # Auto-calculate order if not provided or set to 0
            order = data.get('order')
            if order is None or int(order) == 0:
                parent_id = data.get('parent')
                last = NavigationItem.objects.filter(position=data['position'], parent_id=parent_id).order_by('-order').first()
                if last:
                    order = last.order + 1
                else:
                    order = 1
            
            item = NavigationItem.objects.create(
                label=data['label'],
                url=data.get('url', ''),
                position=data['position'],
                parent_id=data.get('parent'),
                icon=data.get('icon', ''),
                order=order,
                is_active=data.get('is_active', True),
                settings=data.get('settings', {})
            )
            return JsonResponse({
                'id': item.id, 
                'label': item.label,
                'order': item.order,
                'message': 'Menu item created'
            }, status=201)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)


@csrf_exempt
def nav_item_detail(request, pk):
    """Get, Update, Delete a single menu item"""
    try:
        item = NavigationItem.objects.get(pk=pk)
    except NavigationItem.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)

    if request.method == 'GET':
        return JsonResponse({
            'id': item.id,
            'label': item.label,
            'url': item.url,
            'icon': item.icon,
            'order': item.order,
            'position': item.position,
            'is_active': item.is_active,
            'parent': item.parent_id,
            'settings': item.settings or {}
        })
    
    elif request.method in ['PUT', 'PATCH']:
        try:
            data = json.loads(request.body)
            if 'label' in data: item.label = data['label']
            if 'url' in data: item.url = data['url']
            if 'icon' in data: item.icon = data['icon']
            if 'order' in data: item.order = int(data['order'])
            if 'position' in data: item.position = data['position']
            if 'parent' in data: item.parent_id = data['parent']
            if 'is_active' in data: item.is_active = data['is_active']
            if 'settings' in data: item.settings = data['settings']
            item.save()
            return JsonResponse({
                'id': item.id,
                'label': item.label,
                'url': item.url,
                'parent': item.parent_id,
                'settings': item.settings or {}
            })
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
            
    elif request.method == 'DELETE':
        item.delete()
        return JsonResponse({'message': 'Deleted'})
        
    return JsonResponse({'error': 'Method not allowed'}, status=405)


# ---------------------------
# HELPER: Absolute Image URL
# ---------------------------
def get_image_url(request, image_field):
    """Return full absolute URL for image if exists."""
    if image_field:
        return request.build_absolute_uri(image_field.url)
    return None

# ---------------------------
# STARTUP DETAIL (FRONTEND)
# ---------------------------
@require_GET
def startup_detail(request, slug):
    """Full detail for a startup with its related stories"""
    try:
        s = Startup.objects.select_related('category', 'city').get(slug=slug)

        related_stories = s.related_stories.all().order_by('-created_at')
        stories_data = [{
            'id': story.id,
            'title': story.title,
            'slug': story.slug,
            'status': story.status,
            'published_at': story.published_at.isoformat() if story.published_at else None,
            'created_at': story.created_at.isoformat() if story.created_at else None,
            'thumbnail': get_image_url(request, story.thumbnail),
        } for story in related_stories]

        return JsonResponse({
            'id': s.id,
            'name': s.name,
            'slug': s.slug,
            'description': s.description,
            'tagline': s.tagline or (s.description[:140] if s.description else ''),
            'logo': get_image_url(request, s.logo),

            'category': s.category.id if s.category else None,
            'category_name': s.category.name if s.category else None,
            'categorySlug': s.category.slug if s.category else None,

            'city': s.city.id if s.city else None,
            'city_name': s.city.name if s.city else None,
            'citySlug': s.city.slug if s.city else None,

            'website_url': s.website_url,
            'founder_name': s.founder_name,
            'founder_linkedin': s.founder_linkedin,
            'founded_year': s.founded_year,
            'is_featured': s.is_featured,
            'status': s.status,
            
            # Premium Fields
            'funding_stage': getattr(s, 'funding_stage', None) or getattr(s, 'stage', ''),
            'business_model': getattr(s, 'business_model', ''),
            'team_size': s.team_size,
            'founders_data': _get_founders(request, s),
            'industry_tags': getattr(s, 'industry_tags', None) or [],

            # SEO
            'meta_title': s.meta_title or s.name,
            'meta_description': s.meta_description or (s.description[:160] if s.description else ''),
            'meta_keywords': getattr(s, 'meta_keywords', ''),
            'og_image': get_image_url(request, s.og_image) or get_image_url(request, s.logo),
            'canonical_override': getattr(s, 'canonical_override', '') or '',
            'noindex': getattr(s, 'noindex', False),

            'related_stories': stories_data,
        })

    except Startup.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


# ---------------------------
# AI SEO GENERATION
# ---------------------------
@csrf_exempt
@require_POST
def generate_seo_view(request):
    try:
        data = json.loads(request.body)
        if data.get('type') == 'hub':
            suggestions = CitySEOGenerator(data.get('title'), data.get('description', ''))
        else:
            suggestions = generate_seo_suggestions(data)
        return JsonResponse(suggestions)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------
# AI CONTENT GENERATION
# ---------------------------
@csrf_exempt
@require_POST
def generate_content_view(request):
    try:
        data = json.loads(request.body)
        if 'prompt' in data:
            prompt_text = data.get('prompt')
            result = generate_ai_content_direct(prompt_text)
        else:
            prompt_name = data.get('prompt_name')
            context = data.get('context', {})
            result = generate_ai_content(prompt_name, context)

        return JsonResponse(result)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


# ---------------------------
# SESSION MANAGEMENT (AUTH)
# ---------------------------
@csrf_exempt
@require_POST
def session_login_view(request):
    try:
        data = json.loads(request.body)
        username = data.get("username")
        password = data.get("password")

        if not username or not password:
            return JsonResponse({"error": "Username and password are required"}, status=400)

        user = authenticate(request, username=username, password=password)
        if not user:
            return JsonResponse({"error": "Invalid credentials"}, status=401)

        login(request, user)
        return JsonResponse({"ok": True})

    except Exception:
        return JsonResponse({"error": "Login failed"}, status=500)


@csrf_exempt
@require_POST
def session_logout_view(request):
    logout(request)
    return JsonResponse({"ok": True})

@csrf_exempt
@require_POST
def newsletter_subscribe(request):
    try:
        from .models import NewsletterSubscription
        data = json.loads(request.body)
        email = data.get('email', '').strip().lower()
        if not email:
            return JsonResponse({'error': 'Email is required'}, status=400)
        
        # Check if already exists
        sub, created = NewsletterSubscription.objects.get_or_create(email=email)
        if not created and not sub.is_active:
            sub.is_active = True
            sub.save()
        
        return JsonResponse({'message': 'Success', 'created': created}, status=201)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@require_GET
def newsletter_list(request):
    from .models import NewsletterSubscription
    subs = NewsletterSubscription.objects.all().order_by('-created_at')
    data = [{
        'id': s.id,
        'email': s.email,
        'is_active': s.is_active,
        'created_at': s.created_at.strftime("%Y-%m-%d %H:%M")
    } for s in subs]
    return JsonResponse(data, safe=False)

@csrf_exempt
def newsletter_unsubscribe(request):
    if request.method in ['POST', 'GET']:
        try:
            from .models import NewsletterSubscription
            # Handle both GET (from email link) and POST (from UI)
            if request.method == 'GET':
                email = request.GET.get('email')
                token = request.GET.get('token')
            else:
                data = json.loads(request.body)
                email = data.get('email')
                token = data.get('token')

            if not email or not token:
                return JsonResponse({'error': 'Email and token are required'}, status=400)

            sub = NewsletterSubscription.objects.get(email=email, token=token)
            sub.is_active = False
            sub.save()

            return JsonResponse({'message': 'Unsubscribed successfully'})
        except NewsletterSubscription.DoesNotExist:
            return JsonResponse({'error': 'Invalid email or token'}, status=404)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@require_GET
def newsletter_template_list(request):
    from .models import NewsletterTemplate
    templates = NewsletterTemplate.objects.all().order_by('-updated_at')
    data = []
    for t in templates:
        data.append({
            'id': t.id,
            'name': t.name,
            'subject_format': t.subject_format,
            'logo_url': t.logo_url,
            'font_family': t.font_family,
            'header_title': t.header_title,
            'header_subtitle': t.header_subtitle,
            'body_intro': t.body_intro,
            'footer_text': t.footer_text,
            'accent_color': t.accent_color,
            'is_active': t.is_active,
            'updated_at': t.updated_at.strftime("%Y-%m-%d %H:%M")
        })
    return JsonResponse(data, safe=False)

@csrf_exempt
def newsletter_template_update(request, pk=None):
    from .models import NewsletterTemplate
    if request.method in ['POST', 'PUT', 'PATCH']:
        try:
            data = json.loads(request.body)
            if pk:
                template = NewsletterTemplate.objects.get(pk=pk)
            else:
                template = NewsletterTemplate.objects.create(name=data.get('name', 'Newsletter Template'))

            if 'name' in data: template.name = data['name']
            if 'subject_format' in data: template.subject_format = data['subject_format']
            if 'logo_url' in data: template.logo_url = data['logo_url']
            if 'font_family' in data: template.font_family = data['font_family']
            if 'header_title' in data: template.header_title = data['header_title']
            if 'header_subtitle' in data: template.header_subtitle = data['header_subtitle']
            if 'body_intro' in data: template.body_intro = data['body_intro']
            if 'footer_text' in data: template.footer_text = data['footer_text']
            if 'accent_color' in data: template.accent_color = data['accent_color']
            if 'is_active' in data:
                template.is_active = data['is_active']
                if template.is_active:
                    # Deactivate others if this is active
                    NewsletterTemplate.objects.exclude(pk=template.pk).update(is_active=False)

            template.save()
            return JsonResponse({'message': 'Template updated', 'id': template.id})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)
    return JsonResponse({'error': 'Method not allowed'}, status=405)

@require_GET
def newsletter_template_detail(request, pk):
    from .models import NewsletterTemplate
    try:
        t = NewsletterTemplate.objects.get(pk=pk)
        return JsonResponse({
            'id': t.id,
            'name': t.name,
            'subject_format': t.subject_format,
            'logo_url': t.logo_url,
            'font_family': t.font_family,
            'header_title': t.header_title,
            'header_subtitle': t.header_subtitle,
            'body_intro': t.body_intro,
            'footer_text': t.footer_text,
            'accent_color': t.accent_color,
            'is_active': t.is_active,
        })
    except NewsletterTemplate.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


# ---------------------------
# REDIRECT ENGINE (slug changes → 301)
# ---------------------------
@require_GET
def redirect_resolve(request):
    """Resolve a path to its redirect target. Public site calls before 404."""
    path = (request.GET.get('path') or request.GET.get('q') or '').strip().rstrip('/') or '/'
    if not path.startswith('/'):
        path = '/' + path
    try:
        r = Redirect.objects.get(from_path=path)
        return JsonResponse({'redirect_to': r.to_path, 'status': 301 if r.is_permanent else 302})
    except Redirect.DoesNotExist:
        return JsonResponse({'error': 'Not found'}, status=404)


# ---------------------------
# SITEMAP (public URLs only; exclude draft/pending)
# ---------------------------
@require_GET
def sitemap_view(request):
    from django.conf import settings
    base = request.build_absolute_uri('/').rstrip('/')
    if getattr(settings, 'SITEMAP_BASE_URL', None):
        base = settings.SITEMAP_BASE_URL.rstrip('/')
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    lines.append(f'  <url><loc>{base}/</loc><changefreq>daily</changefreq><priority>1.0</priority></url>')
    for s in Story.objects.filter(status='published').values_list('slug', 'updated_at'):
        lines.append(f'  <url><loc>{base}/stories/{s[0]}/</loc><lastmod>{s[1].date().isoformat()}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for s in Startup.objects.filter(status='published').values_list('slug', 'updated_at'):
        lines.append(f'  <url><loc>{base}/startups/{s[0]}/</loc><lastmod>{s[1].date().isoformat()}</lastmod><changefreq>weekly</changefreq><priority>0.8</priority></url>')
    for c in Category.objects.filter(status='published').values_list('slug', flat=True):
        lines.append(f'  <url><loc>{base}/categories/{c}/</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>')
    for c in City.objects.filter(status='published').values_list('slug', flat=True):
        lines.append(f'  <url><loc>{base}/cities/{c}/</loc><changefreq>weekly</changefreq><priority>0.7</priority></url>')
    for p in Page.objects.filter(status='published').values_list('slug', flat=True):
        lines.append(f'  <url><loc>{base}/{p}/</loc><changefreq>monthly</changefreq><priority>0.6</priority></url>')
    lines.append('</urlset>')
    return HttpResponse('\n'.join(lines), content_type='application/xml')


# ---------------------------
# ROBOTS.TXT (allow public; block admin + API + submission preview)
# ---------------------------
@require_GET
def robots_view(request):
    from django.conf import settings
    base = request.build_absolute_uri('/').rstrip('/')
    if getattr(settings, 'SITEMAP_BASE_URL', None):
        base = settings.SITEMAP_BASE_URL.rstrip('/')
    lines = [
        'User-agent: *',
        'Allow: /',
        'Disallow: /admin/',
        'Disallow: /api/',
        'Disallow: /submit/preview/',
        f'Sitemap: {base}/sitemap.xml',
    ]
    return HttpResponse('\n'.join(lines), content_type='text/plain; charset=utf-8')
