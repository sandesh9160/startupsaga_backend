from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from .api_views import (
    story_list, story_detail, trending_stories,
    startup_list, startup_create, startup_detail,
    category_list, category_detail, city_list, city_detail, category_create,
    page_list, page_detail,
    sections_list, section_create, section_update, section_delete,
    submit_startup, nav_items_list,
    footer_list, seo_settings_list, media_list,
    prompt_list, prompt_create, prompt_update, prompt_delete, prompt_detail, prompt_defaults,
    prompt_apply_all,
    layout_settings_list, theme_settings,
    submission_list, submission_detail, submission_update, update_submission_status, submission_delete,
    city_create, city_update, city_delete, category_update, category_delete,
    story_create, story_update, story_delete,
    startup_update, startup_delete,
    page_create, page_update, page_delete, page_detail_admin,
    nav_item_create, nav_item_detail, menu_positions,
    layout_settings_update, seo_settings_update,
    seo_apply_all,
    generate_seo_view, generate_content_view, session_login_view, session_logout_view,
    newsletter_subscribe, newsletter_list, newsletter_unsubscribe,
    newsletter_template_list, newsletter_template_update, newsletter_template_detail,
    redirect_resolve, sitemap_view, robots_view,
)
from .activity_stats import activity_stats, platform_stats

urlpatterns = [
    # Platform Analytics
    path('platform-stats/', platform_stats, name='platform_stats'),
    # AI (spec: /api/ai/*)
    path('ai/generate-seo/', generate_seo_view, name='ai_generate_seo'),
    path('ai/generate-content/', generate_content_view, name='ai_generate_content'),
    path('ai/prompts/', prompt_list, name='ai_prompts'),
    path('ai/prompts/<int:pk>/', prompt_detail, name='ai_prompt_detail'),
    # Legacy AI paths (backward compat)
    path('generate-seo/', generate_seo_view, name='generate_seo'),
    path('generate-content/', generate_content_view, name='generate_content'),

    # Redirect engine (public site checks before 404)
    path('redirect-resolve/', redirect_resolve, name='redirect_resolve'),
    path('sitemap.xml', sitemap_view, name='sitemap'),
    path('robots.txt', robots_view, name='robots'),

    # JWT (spec: JWT authentication)
    path('token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),

    # Session auth (dashboard fallback)
    path('session-login/', session_login_view, name='session_login'),
    path('session-logout/', session_logout_view, name='session_logout'),

    # Story CRUD endpoints
    path('stories/', story_list, name='story_list'),
    path('stories/create/', story_create, name='story_create'),
    path('stories/trending/', trending_stories, name='trending_stories'),
    path('stories/<slug:slug>/', story_detail, name='story_detail'),
    path('stories/<int:story_id>/update/', story_update, name='story_update'),
    path('stories/<int:story_id>/delete/', story_delete, name='story_delete'),

    # Startup CRUD endpoints

    path('startups/', startup_list, name='startup_list'),
    path('startups/create/', startup_create, name='startup_create'),
    path('startups/<slug:slug>/', startup_detail, name='startup_detail'),
    path('startups/<slug:slug>/update/', startup_update, name='startup_update'),
    path('startups/<slug:slug>/delete/', startup_delete, name='startup_delete'),

    # Category CRUD endpoints

    path('categories/', category_list, name='category_list'),
    path('categories/create/', category_create, name='category_create'),
    path('categories/<slug:slug>/', category_detail, name='category_detail'),
    path('categories/<slug:slug>/update/', category_update, name='category_update'),
    path('categories/<slug:slug>/delete/', category_delete, name='category_delete'),


    # City CRUD endpoints
    path('cities/', city_list, name='city_list'),
    path('cities/create/', city_create, name='city_create'),
    path('cities/<slug:slug>/', city_detail, name='city_detail'),
    path('cities/<slug:slug>/update/', city_update, name='city_update'),
    path('cities/<slug:slug>/delete/', city_delete, name='city_delete'),

    #Page CRUD endpoints
    path('pages/', page_list, name='page_list'),
    path('pages/create/', page_create, name='page_create'),
    path('pages/<int:pk>/', page_detail_admin, name='page_detail_admin'),
    path('pages/<slug:slug>/', page_detail, name='page_detail'),
    path('pages/<int:pk>/update/', page_update, name='page_update'),
    path('pages/<int:pk>/delete/', page_delete, name='page_delete'),

    #Section CRUD endpoints
    path('sections/', sections_list, name='sections_list'),
    path('sections/create/', section_create, name='section_create'),
    path('sections/<int:pk>/update/', section_update, name='section_update'),
    path('sections/<int:pk>/delete/', section_delete, name='section_delete'),
    
    # Submission endpoints
    path('submissions/list/', submission_list, name='submission_list'),
    path('submissions/<int:pk>/', submission_detail, name='submission_detail'),
    path('submissions/<int:pk>/update/', submission_update, name='submission_update'),
    path('submissions/<int:pk>/status/', update_submission_status, name='update_submission_status'),
    path('submissions/<int:pk>/delete/', submission_delete, name='submission_delete'),
    path('submissions/create/', submit_startup, name='submit_startup'),
    
    # Navigation
    path('navigation/', nav_items_list, name='nav_items_list'),
    path('navigation/positions/', menu_positions, name='menu_positions'),
    path('navigation/create/', nav_item_create, name='nav_item_create'),
    path('navigation/<int:pk>/', nav_item_detail, name='nav_item_detail'),

    # Other settings
    path('footer/', footer_list, name='footer_list'),
    path('seo-settings/', seo_settings_list, name='seo_settings_list'),
    path('seo-settings/update/', seo_settings_update, name='seo_settings_update'),
    path('seo-settings/apply-all/', seo_apply_all, name='seo_apply_all'),
    path('media/', media_list, name='media_list'),
    

    # Prompt CRUD endpoints
    path('prompts/', prompt_list, name='prompt_list'),
    path('prompts/defaults/', prompt_defaults, name='prompt_defaults'),
    path('prompts/create/', prompt_create, name='prompt_create'),
    path('prompts/apply-all/', prompt_apply_all, name='prompt_apply_all'),
    path('prompts/<int:pk>/', prompt_detail, name='prompt_detail'),
    path('prompts/<int:pk>/update/', prompt_update, name='prompt_update'),
    path('prompts/<int:pk>/delete/', prompt_delete, name='prompt_delete'),
    
    
    # Other settings
    path('layout-settings/', layout_settings_list, name='layout_settings_list'),
    path('layout-settings/update/', layout_settings_update, name='layout_settings_update'),
    path('theme/', theme_settings, name='theme_settings'),
    path('auth/signout/', session_logout_view, name='session_logout'),
    path('newsletter/subscribe/', newsletter_subscribe, name='newsletter_subscribe'),
    path('newsletter/list/', newsletter_list, name='newsletter_list'),
    path('newsletter/unsubscribe/', newsletter_unsubscribe, name='newsletter_unsubscribe'),
    path('newsletter/templates/', newsletter_template_list, name='newsletter_template_list'),
    path('newsletter/templates/create/', newsletter_template_update, name='newsletter_template_create'),
    path('newsletter/templates/<int:pk>/', newsletter_template_detail, name='newsletter_template_detail'),
    path('newsletter/templates/<int:pk>/update/', newsletter_template_update, name='newsletter_template_update'),
    
    # Dashboard Analytics
    path('activity-stats/', activity_stats, name='activity_stats'),
]
