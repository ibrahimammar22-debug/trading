/**
 * Solenne Theme — theme.js
 * Scroll animations, header behavior, mobile nav
 */

(function () {
  'use strict';

  /* ── Utility ─────────────────────────────────── */
  function qs(selector, context) {
    return (context || document).querySelector(selector);
  }

  function qsa(selector, context) {
    return Array.from((context || document).querySelectorAll(selector));
  }

  function on(el, event, handler, opts) {
    if (!el) return;
    el.addEventListener(event, handler, opts || false);
  }

  /* ── Header scroll behavior ───────────────────── */
  function initHeaderScroll() {
    var header = qs('#site-header');
    if (!header) return;

    var scrollThreshold = 60;
    var ticking = false;

    function updateHeader() {
      if (window.scrollY > scrollThreshold) {
        header.classList.add('scrolled');
      } else {
        header.classList.remove('scrolled');
      }
      ticking = false;
    }

    on(window, 'scroll', function () {
      if (!ticking) {
        requestAnimationFrame(updateHeader);
        ticking = true;
      }
    }, { passive: true });

    // Run once on init
    updateHeader();
  }

  /* ── Mobile navigation ────────────────────────── */
  function initMobileNav() {
    var toggle = qs('#nav-toggle');
    var nav = qs('#site-nav');
    var overlay = qs('#nav-overlay');

    if (!toggle || !nav) return;

    function openNav() {
      nav.classList.add('is-open');
      toggle.setAttribute('aria-expanded', 'true');
      if (overlay) {
        overlay.classList.add('active');
        overlay.removeAttribute('aria-hidden');
      }
      document.body.style.overflow = 'hidden';
    }

    function closeNav() {
      nav.classList.remove('is-open');
      toggle.setAttribute('aria-expanded', 'false');
      if (overlay) {
        overlay.classList.remove('active');
        overlay.setAttribute('aria-hidden', 'true');
      }
      document.body.style.overflow = '';
    }

    on(toggle, 'click', function () {
      var isOpen = nav.classList.contains('is-open');
      if (isOpen) {
        closeNav();
      } else {
        openNav();
      }
    });

    if (overlay) {
      on(overlay, 'click', closeNav);
    }

    // Close on Escape key
    on(document, 'keydown', function (e) {
      if (e.key === 'Escape' && nav.classList.contains('is-open')) {
        closeNav();
        toggle.focus();
      }
    });

    // Close when nav link is clicked
    qsa('.site-nav__link', nav).forEach(function (link) {
      on(link, 'click', closeNav);
    });

    // Close on viewport resize to desktop
    var mql = window.matchMedia('(min-width: 769px)');
    mql.addEventListener('change', function (e) {
      if (e.matches) {
        closeNav();
      }
    });
  }

  /* ── Scroll reveal animations ─────────────────── */
  function initScrollReveal() {
    var prefersReducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    if (prefersReducedMotion) {
      // Make everything visible immediately
      qsa('.fade-in-up, .reveal-up, .reveal-left, .reveal-right').forEach(function (el) {
        el.classList.add('is-visible');
      });
      return;
    }

    var observerOptions = {
      root: null,
      rootMargin: '0px 0px -80px 0px',
      threshold: 0.1
    };

    var observer = new IntersectionObserver(function (entries) {
      entries.forEach(function (entry) {
        if (entry.isIntersecting) {
          entry.target.classList.add('is-visible');
          observer.unobserve(entry.target);
        }
      });
    }, observerOptions);

    qsa('.fade-in-up, .reveal-up, .reveal-left, .reveal-right').forEach(function (el) {
      observer.observe(el);
    });
  }

  /* ── Smooth anchor scrolling ──────────────────── */
  function initSmoothAnchors() {
    qsa('a[href^="#"]').forEach(function (anchor) {
      on(anchor, 'click', function (e) {
        var href = this.getAttribute('href');
        if (href === '#') return;

        var target = qs(href);
        if (!target) return;

        e.preventDefault();
        var headerHeight = parseInt(
          getComputedStyle(document.documentElement).getPropertyValue('--header-height') || '80'
        );

        var targetTop = target.getBoundingClientRect().top + window.pageYOffset - headerHeight;

        window.scrollTo({
          top: targetTop,
          behavior: 'smooth'
        });

        // Update focus for accessibility
        target.setAttribute('tabindex', '-1');
        target.focus({ preventScroll: true });
      });
    });
  }

  /* ── Cart AJAX (Shopify) ─────────────────────── */
  function initCartForms() {
    qsa('.product-form').forEach(function (form) {
      on(form, 'submit', function (e) {
        e.preventDefault();

        var submitBtn = form.querySelector('[type="submit"]');
        var originalText = submitBtn ? submitBtn.textContent.trim() : 'Add to Cart';

        if (submitBtn) {
          submitBtn.disabled = true;
          submitBtn.textContent = 'Adding...';
        }

        var formData = new FormData(form);

        fetch('/cart/add.js', {
          method: 'POST',
          body: formData
        })
          .then(function (res) {
            if (!res.ok) {
              return res.json().then(function (data) {
                throw new Error(data.description || 'Could not add to cart.');
              });
            }
            return res.json();
          })
          .then(function () {
            // Success — update cart count
            return fetch('/cart.js');
          })
          .then(function (res) { return res.json(); })
          .then(function (cart) {
            updateCartCount(cart.item_count);
            if (submitBtn) {
              submitBtn.textContent = 'Added!';
              setTimeout(function () {
                submitBtn.textContent = originalText;
                submitBtn.disabled = false;
              }, 2000);
            }
          })
          .catch(function (err) {
            console.error('Cart error:', err);
            if (submitBtn) {
              submitBtn.textContent = 'Error — Try Again';
              submitBtn.disabled = false;
              setTimeout(function () {
                submitBtn.textContent = originalText;
              }, 3000);
            }
          });
      });
    });
  }

  function updateCartCount(count) {
    var cartCountEl = qs('.cart-count');
    var cartIconEl = qs('.cart-icon');

    if (!cartIconEl) return;

    if (count > 0) {
      if (!cartCountEl) {
        cartCountEl = document.createElement('span');
        cartCountEl.className = 'cart-count';
        cartCountEl.setAttribute('aria-hidden', 'true');
        cartIconEl.appendChild(cartCountEl);
      }
      cartCountEl.textContent = count;
      cartIconEl.setAttribute('aria-label', 'Cart (' + count + ' items)');
    } else if (cartCountEl) {
      cartCountEl.remove();
      cartIconEl.setAttribute('aria-label', 'Cart');
    }
  }

  /* ── Video lazy loading ───────────────────────── */
  function initVideoObserver() {
    var videos = qsa('video.hero__video');
    if (!videos.length) return;

    if ('IntersectionObserver' in window) {
      var videoObserver = new IntersectionObserver(function (entries) {
        entries.forEach(function (entry) {
          if (entry.isIntersecting) {
            var video = entry.target;
            if (video.paused) {
              video.play().catch(function () {
                // Autoplay was blocked — silently fail
              });
            }
          } else {
            var video = entry.target;
            if (!video.paused) {
              video.pause();
            }
          }
        });
      }, { threshold: 0.25 });

      videos.forEach(function (video) {
        videoObserver.observe(video);
      });
    }
  }

  /* ── Init ─────────────────────────────────────── */
  function init() {
    initHeaderScroll();
    initMobileNav();
    initScrollReveal();
    initSmoothAnchors();
    initCartForms();
    initVideoObserver();
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

})();
