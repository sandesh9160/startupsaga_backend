from django.db import models
from django.utils.text import slugify
from django.contrib.auth.models import User

class Category(models.Model):
    STATUS_CHOICES = (('draft', 'Draft'), ('published', 'Published'))
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    description = models.TextField(blank=True)
    icon = models.ImageField(upload_to='categories/icons/', blank=True, null=True)
    icon_name = models.CharField(max_length=50, blank=True, default='', help_text='Lucide icon name e.g. credit-card, cloud, shopping-cart')
    is_featured = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True, help_text='Comma-separated SEO keywords')
    og_image = models.ImageField(upload_to='seo/og_images/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name).lower().replace(' ', '-')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Categories"

class City(models.Model):
    STATUS_CHOICES = (('draft', 'Draft'), ('published', 'Published'))
    TIER_CHOICES = (
        ('1', 'Tier 1'),
        ('2', 'Tier 2'),
        ('3', 'Tier 3'),
    )
    name = models.CharField(max_length=100)
    slug = models.SlugField(unique=True, blank=True)
    tier = models.CharField(max_length=1, choices=TIER_CHOICES, default='1')
    startup_count = models.IntegerField(default=0)
    unicorn_count = models.IntegerField(default=0)
    description = models.TextField(blank=True)
    image = models.ImageField(upload_to='cities/images/', blank=True, null=True)
    is_featured = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True, help_text='Comma-separated SEO keywords')
    og_image = models.ImageField(upload_to='seo/og_images/', blank=True, null=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name).lower().replace(' ', '-')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Cities"

class Startup(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('published', 'Published'),
        ('blocked', 'Blocked'),
    )
    BUSINESS_MODEL_CHOICES = (
        ('b2b', 'B2B'),
        ('b2c', 'B2C'),
        ('b2b2c', 'B2B2C'),
        ('d2c', 'D2C'),
        ('saas', 'SaaS'),
        ('marketplace', 'Marketplace'),
        ('subscription', 'Subscription'),
        ('freemium', 'Freemium'),
        ('platform', 'Platform'),
        ('other', 'Other'),
    )

    name = models.CharField(max_length=200)
    slug = models.SlugField(unique=True, blank=True)
    logo = models.ImageField(upload_to='startups/logos/', blank=True, null=True)
    tagline = models.CharField(max_length=300, blank=True)
    description = models.TextField()
    website_url = models.URLField(blank=True)
    founded_year = models.IntegerField(blank=True, null=True)
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, related_name='startups')
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='startups')
    funding_stage = models.CharField(max_length=100, blank=True, help_text='e.g. Seed, Series A, Unicorn')
    business_model = models.CharField(max_length=30, choices=BUSINESS_MODEL_CHOICES, blank=True)
    team_size = models.CharField(max_length=100, blank=True)
    industry_tags = models.JSONField(blank=True, null=True, help_text='List of industry tag strings')
    founders_data = models.JSONField(blank=True, null=True, help_text='List of founders: [{"name": "...", "role": "...", "linkedin": "...", "image": "..."}]')
    
    founder_name = models.CharField(max_length=200, blank=True)  # Legacy
    founder_linkedin = models.URLField(blank=True)  # Legacy
    is_featured = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True, help_text='Comma-separated SEO keywords')
    og_image = models.ImageField(upload_to='seo/og_images/', blank=True, null=True)
    image_alt = models.CharField(max_length=300, blank=True, help_text='Alt text for logo/featured image')
    canonical_override = models.URLField(blank=True)
    noindex = models.BooleanField(default=False)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name).lower().replace(' ', '-')
        else:
            self.slug = self.slug.lower().replace(' ', '-')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class Founder(models.Model):
    """Founder profile linked to a startup."""
    name = models.CharField(max_length=200)
    designation = models.CharField(max_length=200, blank=True)
    bio = models.TextField(blank=True)
    linkedin = models.URLField(blank=True)
    photo = models.ImageField(upload_to='founders/photos/', blank=True, null=True)
    startup = models.ForeignKey('Startup', on_delete=models.CASCADE, null=True, blank=True, related_name='founders')
    order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['order', 'name']

    def __str__(self):
        return self.name


class Story(models.Model):
    STATUS_CHOICES = (
        ('draft', 'Draft'),
        ('pending', 'Pending'),
        ('published', 'Published'),
        ('archived', 'Archived'),
    )

    title = models.CharField(max_length=300)
    slug = models.SlugField(unique=True, blank=True)
    excerpt = models.TextField(blank=True)
    content = models.TextField()
    thumbnail = models.ImageField(upload_to='stories/thumbnails/', blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='stories')
    city = models.ForeignKey(City, on_delete=models.SET_NULL, null=True, related_name='stories')
    related_startup = models.ForeignKey(Startup, on_delete=models.SET_NULL, null=True, blank=True, related_name='related_stories')
    author = models.CharField(max_length=200, blank=True, default='Editorial Team')
    read_time = models.PositiveIntegerField(blank=True, null=True, help_text='Read time in minutes')
    sections = models.JSONField(blank=True, null=True, help_text="Structured sections: The Problem, The Solution, Founder Journey, etc.")
    
    # SEO
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    meta_keywords = models.TextField(blank=True, help_text='Comma-separated SEO keywords')
    image_alt = models.CharField(max_length=300, blank=True, help_text='Alt text for featured image')
    show_table_of_contents = models.BooleanField(default=True)
    og_image = models.ImageField(upload_to='seo/og_images/', blank=True, null=True)
    canonical_override = models.URLField(blank=True, help_text='Override canonical URL')
    noindex = models.BooleanField(default=False)
    
    is_featured = models.BooleanField(default=False)
    stage = models.CharField(max_length=50, blank=True)
    view_count = models.IntegerField(default=0)
    trending_score = models.FloatField(default=0.0)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')
    published_at = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title).lower().replace(' ', '-')
        else:
            self.slug = self.slug.lower().replace(' ', '-')
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name_plural = "Stories"

class StartupSubmission(models.Model):
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    )

    startup_name = models.CharField(max_length=200)
    founder_name = models.CharField(max_length=200)
    email = models.EmailField()
    website = models.URLField(blank=True)
    description = models.TextField(blank=True, help_text='Short description')
    full_story = models.TextField(blank=True, help_text='Full startup story')
    city = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, blank=True)
    funding_stage = models.CharField(max_length=100, blank=True)
    business_model = models.CharField(max_length=50, blank=True)
    logo = models.ImageField(upload_to='submissions/logos/', blank=True, null=True)
    thumbnail = models.ImageField(upload_to='submissions/thumbnails/', blank=True, null=True)
    
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.startup_name} ({self.status})"

class Page(models.Model):
    """Static CMS pages: About, Contact, Privacy, Terms, custom landings."""
    STATUS_CHOICES = (('draft', 'Draft'), ('published', 'Published'))
    title = models.CharField(max_length=200)
    slug = models.SlugField(unique=True)
    content = models.TextField(blank=True)
    meta_title = models.CharField(max_length=200, blank=True)
    meta_description = models.TextField(blank=True)
    og_image = models.ImageField(upload_to='pages/og/', blank=True, null=True)
    canonical_override = models.URLField(blank=True)
    noindex = models.BooleanField(default=False)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='published')
    theme_overrides = models.JSONField(blank=True, null=True, help_text='Per-page styling: bg_color, font_family, accent_color, etc.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ['title']


class PageThemeOverride(models.Model):
    """Theme overrides for built-in pages (homepage, stories list, etc.) - no Page record needed."""
    PAGE_KEY_CHOICES = (
        ('homepage', 'Homepage'),
        ('stories_list', 'Stories Listing'),
        ('stories_detail', 'Story Detail'),
        ('startups_list', 'Startups Listing'),
        ('startups_detail', 'Startup Detail'),
        ('categories_list', 'Categories Listing'),
        ('categories_detail', 'Category Detail'),
        ('cities_list', 'Cities Listing'),
        ('cities_detail', 'City Detail'),
        ('submit', 'Submit Page'),
    )
    page_key = models.CharField(max_length=50, unique=True, choices=PAGE_KEY_CHOICES)
    theme_overrides = models.JSONField(blank=True, null=True, help_text='bg_color, font_family, accent_color, dropdown_style, etc.')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Theme: {self.get_page_key_display()}"


class PageSection(models.Model):
    PAGE_CHOICES = (
        ('homepage', 'Homepage'),
        ('stories', 'Stories Listing'),
        ('startups', 'Startups Listing'),
        ('city', 'City Detail'),
        ('category', 'Category Detail'),
        ('footer', 'Footer'),
        ('custom', 'Custom Page'),
    )
    
    SECTION_TYPE_CHOICES = (
        ('hero', 'Hero Section'),
        ('banner', 'Hero Banner'),
        ('featured_stories', 'Featured Stories'),
        ('latest_stories', 'Latest Stories'),
        ('category_grid', 'Category Grid'),
        ('city_grid', 'City Grid (Top Cities)'),
        ('rising_hubs', 'Rising Startup Hubs (Tier 2/3)'),
        ('startup_cards', 'Startup Cards'),
        ('featured_startups', 'Featured Startups'),
        ('cta', 'Call to Action'),
        ('newsletter', 'Newsletter Section'),
        ('custom_content', 'Custom Content Block'),
        ('icons', 'Icons Grid'),
        ('testimonials', 'Testimonials'),
        ('footer_content', 'Footer Content'),
        ('text_block', 'Text Block'),
        ('text', 'Text Content'),
        ('image', 'Image Block'),
        ('video', 'Video Block'),

        # About page section types
        ('mission_vision', 'Mission & Vision Cards'),
        ('stats_bar', 'Statistics Bar'),
        ('team_grid', 'Team Grid'),
        ('values_grid', 'Values Grid'),
        
        # Policy / rich content page section types
        ('policy_section', 'Policy Text Section'),
        ('faq', 'FAQ Accordion'),
        ('callout', 'Callout / Highlight Box'),
        ('related_cards', 'Related Content Cards'),
        ('image_gallery', 'Image Gallery'),
        ('table_of_contents', 'Table of Contents'),
    )

    page = models.CharField(max_length=50, choices=PAGE_CHOICES)
    page_obj = models.ForeignKey(Page, on_delete=models.CASCADE, null=True, blank=True, related_name='sections')
    section_type = models.CharField(max_length=50, choices=SECTION_TYPE_CHOICES)
    title = models.CharField(max_length=200, blank=True)
    subtitle = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    content = models.TextField(blank=True, help_text='For custom_content type')
    image = models.ImageField(upload_to='sections/images/', blank=True, null=True)
    icon = models.ImageField(upload_to='sections/icons/', blank=True, null=True)
    link_text = models.CharField(max_length=100, blank=True)
    link_url = models.CharField(max_length=300, blank=True)
    
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(blank=True, null=True, help_text='Section styling: bg_color, font_size, border_radius, dropdown_style, etc.')

    class Meta:
        ordering = ['page', 'order']

    def __str__(self):
        return f"{self.get_page_display()} - {self.get_section_type_display()} ({self.title})"

class NavigationItem(models.Model):
    POSITION_CHOICES = (
        ('header', 'Main Header'),
        ('footer', 'Main Footer'),
        ('footer_company', 'Footer Company'),
        ('footer_links', 'Footer Quick Links'),
        ('sidebar', 'Main Sidebar'),
        ('dashboard_sidebar', 'Dashboard Sidebar'),
    )
    
    label = models.CharField(max_length=100)
    url = models.CharField(max_length=255, blank=True)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, null=True, blank=True, related_name='children')
    icon = models.CharField(max_length=50, blank=True, help_text="Lucide icon name")
    order = models.IntegerField(default=0)
    position = models.CharField(max_length=50, choices=POSITION_CHOICES)
    is_active = models.BooleanField(default=True)
    settings = models.JSONField(blank=True, null=True, help_text='Custom styling: color, weight, is_mega_menu, etc.')

    class Meta:
        ordering = ['order']

    def __str__(self):
        return f"{self.label} ({self.get_position_display()}) - Order: {self.order}"

class AIPrompt(models.Model):
    PROMPT_CATEGORIES = (
        ('story_write', 'Story Writing'),
        ('seo_gen', 'SEO Generation'),
        ('desc_gen', 'Description Generation'),
        ('general', 'General'),
    )
    name = models.CharField(max_length=100, unique=True)
    prompt_text = models.TextField()
    category = models.CharField(max_length=50, choices=PROMPT_CATEGORIES, default='general')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "AI Prompt"
        verbose_name_plural = "AI Prompts"

    def __str__(self):
        return self.name


class FooterSetting(models.Model):
    """Footer sections and content - Shopify-style control."""
    title = models.CharField(max_length=100)
    content = models.TextField(blank=True, help_text='HTML or plain text')
    column_order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['column_order']


class SEOSetting(models.Model):
    """Global SEO defaults."""
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(blank=True)
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.key


class MediaItem(models.Model):
    """Media library for admin-managed assets."""
    title = models.CharField(max_length=200)
    file = models.FileField(upload_to='media/')
    file_type = models.CharField(max_length=50, blank=True)
    alt_text = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

class LayoutSetting(models.Model):
    key = models.CharField(max_length=100, unique=True)
    value = models.TextField(help_text="Can be a string, hex color, or JSON")
    setting_type = models.CharField(max_length=50, choices=(
        ('color', 'Color'),
        ('text', 'Text'),
        ('boolean', 'Switch'),
        ('json', 'Complex JSON'),
    ), default='text')
    description = models.CharField(max_length=255, blank=True)

    def __str__(self):
        return self.key


import uuid
class NewsletterSubscription(models.Model):
    email = models.EmailField(unique=True)
    token = models.UUIDField(default=uuid.uuid4, unique=True, editable=False)
    is_active = models.BooleanField(default=True)
    last_sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.email} ({'Active' if self.is_active else 'Inactive'})"


class NewsletterTemplate(models.Model):
    name = models.CharField(max_length=100, default="Weekly Newsletter")
    subject_format = models.CharField(max_length=255, default="StartupSaga Weekly: {first_story_title}")
    logo_url = models.URLField(blank=True, null=True)
    font_family = models.CharField(max_length=255, default="-apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif")
    header_title = models.CharField(max_length=255, default="StartupSaga")
    header_subtitle = models.CharField(max_length=255, default="Weekly stories, founder insights, and ecosystem updates")
    body_intro = models.CharField(max_length=255, default="Top Stories This Week")
    footer_text = models.TextField(default="© {year} StartupSaga. All rights reserved.\nYou received this email because you subscribed to our newsletter.")
    accent_color = models.CharField(max_length=7, default="#ea580c")
    is_active = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"

class Redirect(models.Model):
    """301 redirects when slugs change. Public site checks this before 404."""
    from_path = models.CharField(max_length=500, unique=True, help_text='e.g. /stories/old-slug')
    to_path = models.CharField(max_length=500, help_text='e.g. /stories/new-slug')
    is_permanent = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['from_path']

    def __str__(self):
        return f"{self.from_path} → {self.to_path}"
