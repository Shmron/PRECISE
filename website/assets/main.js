/* ============================================================
   Place Alert Labs — Shared JavaScript
   Extracted from app.blade.php layout
   ============================================================ */

// ── AOS Initialisation ──────────────────────────────────────
if (typeof AOS !== 'undefined') {
    AOS.init({ duration: 800, easing: 'ease-in-out', once: true });
}

// ── Bootstrap Icons initialisation ─────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const allIcons = document.querySelectorAll('i[class*="bi-"]');
    allIcons.forEach(icon => {
        if (!icon.style.fontFamily) icon.style.fontFamily = '"bootstrap-icons"';
        if (!icon.style.fontWeight) icon.style.fontWeight = 'normal';
    });
});

// ── Mobile menu ─────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const toggle   = document.getElementById('mobile-menu-toggle');
    const navMenu  = document.getElementById('nav-menu');
    if (!toggle || !navMenu) return;

    toggle.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation();
        navMenu.classList.toggle('active');
        const icon = toggle.querySelector('i');
        icon.classList.toggle('bi-list',   !navMenu.classList.contains('active'));
        icon.classList.toggle('bi-x-lg',   navMenu.classList.contains('active'));
    });

    document.addEventListener('click', function (e) {
        if (!navMenu.contains(e.target) && !toggle.contains(e.target)) {
            navMenu.classList.remove('active');
            const icon = toggle.querySelector('i');
            icon.classList.remove('bi-x-lg');
            icon.classList.add('bi-list');
        }
    });

    window.addEventListener('resize', function () {
        if (window.innerWidth > 768) {
            navMenu.classList.remove('active');
            const icon = toggle.querySelector('i');
            icon.classList.remove('bi-x-lg');
            icon.classList.add('bi-list');
        }
    });
});

// ── Active nav link detection ───────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const currentPath = window.location.pathname;
    document.querySelectorAll('.nav-item').forEach(item => item.classList.remove('active'));
    document.querySelectorAll('.nav-link').forEach(link => {
        const href = link.getAttribute('href');
        if (href === currentPath || (currentPath === '/' && href === '/') ||
            (currentPath !== '/' && href !== '/' && href && currentPath.startsWith(href.replace('.html', '')))) {
            link.closest('.nav-item')?.classList.add('active');
        }
    });
    // Also check dropdown items
    document.querySelectorAll('.dropdown-item').forEach(item => {
        const href = item.getAttribute('href');
        if (href && href === currentPath) {
            item.closest('.nav-item')?.classList.add('active');
        }
    });
});

// ── Dropdown handling ───────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(item => {
        const navLink  = item.querySelector('.nav-link');
        const dropdown = item.querySelector('.dropdown');
        if (!dropdown) return;
        navLink.addEventListener('click', e => {
            e.preventDefault();
            navItems.forEach(other => { if (other !== item) other.classList.remove('dropdown-open'); });
            item.classList.toggle('dropdown-open');
        });
        document.addEventListener('click', e => {
            if (!item.contains(e.target)) item.classList.remove('dropdown-open');
        });
        dropdown.querySelectorAll('.dropdown-item').forEach(di => {
            di.addEventListener('click', () => item.classList.remove('dropdown-open'));
        });
    });
});

// ── Scroll-responsive header ────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const header = document.querySelector('.header');
    if (!header) return;
    window.addEventListener('scroll', function () {
        header.classList.toggle('scrolled', window.pageYOffset > 100);
    });
});

// ── Search overlay ──────────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const searchToggle  = document.getElementById('search-toggle');
    const searchOverlay = document.getElementById('search-overlay');
    const searchClose   = document.getElementById('search-close');
    const searchInput   = document.getElementById('search-input');
    if (!searchToggle || !searchOverlay) return;

    searchToggle.addEventListener('click', function () {
        searchOverlay.classList.add('active');
        if (searchInput) searchInput.focus();
        document.body.style.overflow = 'hidden';
    });
    searchClose?.addEventListener('click', function () {
        searchOverlay.classList.remove('active');
        document.body.style.overflow = 'auto';
    });
    searchOverlay.addEventListener('click', function (e) {
        if (e.target === searchOverlay) {
            searchOverlay.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    });
    document.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && searchOverlay.classList.contains('active')) {
            searchOverlay.classList.remove('active');
            document.body.style.overflow = 'auto';
        }
    });
    if (searchInput) {
        searchInput.addEventListener('input', function () {
            const query = this.value.toLowerCase();
            document.querySelectorAll('.suggestion-item').forEach(item => {
                item.style.display = (query && !item.textContent.toLowerCase().includes(query)) ? 'none' : 'flex';
            });
        });
    }
});

// ── Intersection observer for fade-in ───────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const observer = new IntersectionObserver(entries => {
        entries.forEach(entry => { if (entry.isIntersecting) entry.target.classList.add('visible'); });
    }, { threshold: 0.1, rootMargin: '0px 0px -50px 0px' });
    document.querySelectorAll('.fade-in').forEach(el => observer.observe(el));
});

// ── Smooth scrolling for anchor links ───────────────────────
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('a[href^="#"]').forEach(anchor => {
        anchor.addEventListener('click', function (e) {
            e.preventDefault();
            const target = document.querySelector(this.getAttribute('href'));
            if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
        });
    });
});

// ── WhatsApp chat button ─────────────────────────────────────
function openWhatsApp() {
    const phone   = '+263782319736';
    const message = 'Hello! I would like to know more about Place Alert Labs research and services.';
    window.open(`https://wa.me/${phone}?text=${encodeURIComponent(message)}`, '_blank');
}

// ── Button ripple effect ─────────────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('.btn').forEach(btn => {
        btn.addEventListener('click', function (e) {
            const ripple = document.createElement('span');
            const rect   = this.getBoundingClientRect();
            const size   = Math.max(rect.width, rect.height);
            ripple.style.cssText = `position:absolute;width:${size}px;height:${size}px;left:${e.clientX - rect.left - size/2}px;top:${e.clientY - rect.top - size/2}px;background:rgba(255,255,255,.3);border-radius:50%;transform:scale(0);animation:ripple .6s linear;pointer-events:none;`;
            this.appendChild(ripple);
            setTimeout(() => ripple.remove(), 600);
        });
    });
    const rippleStyle = document.createElement('style');
    rippleStyle.textContent = '@keyframes ripple{to{transform:scale(4);opacity:0;}}';
    document.head.appendChild(rippleStyle);
});

// ── Hero slider (for home page) ─────────────────────────────
document.addEventListener('DOMContentLoaded', function () {
    const slides = document.querySelectorAll('.hero-slide');
    const dots   = document.querySelectorAll('.dot');
    if (!slides.length) return;
    let currentSlide = 0, slideInterval;

    function showSlide(index) {
        slides.forEach(s => s.classList.remove('active'));
        dots.forEach(d => d.classList.remove('active'));
        slides[index].classList.add('active');
        if (dots[index]) dots[index].classList.add('active');
        currentSlide = index;
    }
    function nextSlide() { showSlide((currentSlide + 1) % slides.length); }
    function startSlider() { slideInterval = setInterval(nextSlide, 10000); }
    function stopSlider()  { clearInterval(slideInterval); }

    dots.forEach((dot, i) => dot.addEventListener('click', () => { showSlide(i); stopSlider(); startSlider(); }));
    const heroSection = document.querySelector('.aas-hero-section');
    if (heroSection) {
        heroSection.addEventListener('mouseenter', stopSlider);
        heroSection.addEventListener('mouseleave', startSlider);
        // Touch/swipe
        let startX = 0;
        heroSection.addEventListener('touchstart', e => { startX = e.touches[0].clientX; });
        heroSection.addEventListener('touchend', e => {
            const diff = startX - e.changedTouches[0].clientX;
            if (Math.abs(diff) > 50) {
                if (diff > 0) nextSlide();
                else showSlide(currentSlide === 0 ? slides.length - 1 : currentSlide - 1);
                stopSlider(); startSlider();
            }
        });
    }
    startSlider();
});
