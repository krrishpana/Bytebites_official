/**
 * ByteBites - Nutrition App JS
 * Common JavaScript functionality for the ByteBites application
 */

document.addEventListener('DOMContentLoaded', function() {
    // Initialize mobile navigation
    initializeMobileNavigation();

    // Initialize tooltips if Bootstrap is available
    if (typeof bootstrap !== 'undefined' && bootstrap.Tooltip) {
        const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
        tooltipTriggerList.map(function(tooltipTriggerEl) {
            return new bootstrap.Tooltip(tooltipTriggerEl);
        });
    }

    // Auto-dismiss alerts after 5 seconds
    setTimeout(function() {
        const alerts = document.querySelectorAll('.alert:not(.alert-permanent)');
        alerts.forEach(function(alert) {
            // Use Bootstrap's dismiss method if available
            if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } else {
                // Fallback to simple display:none
                alert.style.display = 'none';
            }
        });
    }, 5000);

    // Image preview functionality for file inputs
    const fileInputs = document.querySelectorAll('input[type="file"][accept*="image"]');
    fileInputs.forEach(function(input) {
        input.addEventListener('change', function(e) {
            const file = e.target.files[0];
            if (file) {
                const reader = new FileReader();
                reader.onload = function(event) {
                    // Check if there's a preview container next to the input
                    let previewContainer = input.nextElementSibling;
                    if (!previewContainer || !previewContainer.classList.contains('image-preview')) {
                        // Create one if it doesn't exist
                        previewContainer = document.createElement('div');
                        previewContainer.classList.add('image-preview', 'mt-2', 'text-center');
                        input.parentNode.insertBefore(previewContainer, input.nextSibling);
                    }

                    // Responsive image preview
                    const maxHeight = window.innerWidth <= 600 ? '150px' : '200px';
                    previewContainer.innerHTML = `
                        <img src="${event.target.result}" class="img-fluid rounded" style="max-height: ${maxHeight}; max-width: 100%;">
                    `;
                };
                reader.readAsDataURL(file);
            }
        });
    });

    // Initialize responsive features
    initializeResponsiveFeatures();

    // Handle orientation changes
    window.addEventListener('orientationchange', function() {
        setTimeout(function() {
            adjustForOrientation();
        }, 100);
    });

    // Handle window resize
    let resizeTimer;
    window.addEventListener('resize', function() {
        clearTimeout(resizeTimer);
        resizeTimer = setTimeout(function() {
            adjustForScreenSize();
        }, 250);
    });
});

/**
 * Initialize mobile navigation functionality
 */
function initializeMobileNavigation() {
    const menuToggle = document.getElementById('menuToggle');
    const navbar = document.getElementById('main-navbar');
    const menuOverlay = document.getElementById('menuOverlay');

    if (menuToggle && navbar) {
        menuToggle.addEventListener('click', function() {
            navbar.classList.toggle('active');
            if (menuOverlay) {
                menuOverlay.classList.toggle('active');
            }

            // Update aria-expanded for accessibility
            const isExpanded = navbar.classList.contains('active');
            menuToggle.setAttribute('aria-expanded', isExpanded);

            // Change icon
            const icon = menuToggle.querySelector('i');
            if (icon) {
                icon.className = isExpanded ? 'fas fa-times' : 'fas fa-bars';
            }

            // Prevent body scroll when menu is open
            document.body.style.overflow = isExpanded ? 'hidden' : '';
        });

        // Close menu when overlay is clicked
        if (menuOverlay) {
            menuOverlay.addEventListener('click', function() {
                navbar.classList.remove('active');
                menuOverlay.classList.remove('active');
                menuToggle.setAttribute('aria-expanded', 'false');

                const icon = menuToggle.querySelector('i');
                if (icon) {
                    icon.className = 'fas fa-bars';
                }

                document.body.style.overflow = '';
            });
        }

        // Close menu when a link is clicked (for single-page navigation)
        const navLinks = navbar.querySelectorAll('a');
        navLinks.forEach(function(link) {
            link.addEventListener('click', function() {
                if (window.innerWidth <= 600) {
                    navbar.classList.remove('active');
                    if (menuOverlay) {
                        menuOverlay.classList.remove('active');
                    }
                    menuToggle.setAttribute('aria-expanded', 'false');

                    const icon = menuToggle.querySelector('i');
                    if (icon) {
                        icon.className = 'fas fa-bars';
                    }

                    document.body.style.overflow = '';
                }
            });
        });
    }
}

/**
 * Initialize responsive features
 */
function initializeResponsiveFeatures() {
    // Touch-friendly interactions
    addTouchFriendlyFeatures();

    // Optimize images for mobile
    optimizeImagesForMobile();

    // Adjust font sizes for readability
    adjustFontSizes();
}

/**
 * Add touch-friendly features for mobile devices
 */
function addTouchFriendlyFeatures() {
    // Add touch feedback to buttons
    const buttons = document.querySelectorAll('button, .btn, .hero-btn');
    buttons.forEach(function(button) {
        button.addEventListener('touchstart', function() {
            this.style.transform = 'scale(0.98)';
        });

        button.addEventListener('touchend', function() {
            this.style.transform = '';
        });
    });

    // Improve card interactions on mobile
    const cards = document.querySelectorAll('.feature-card, .card');
    cards.forEach(function(card) {
        card.addEventListener('touchstart', function() {
            this.style.transform = 'translateY(-2px)';
        });

        card.addEventListener('touchend', function() {
            setTimeout(() => {
                this.style.transform = '';
            }, 150);
        });
    });
}

/**
 * Optimize images for mobile viewing
 */
function optimizeImagesForMobile() {
    const images = document.querySelectorAll('img');
    images.forEach(function(img) {
        // Add loading="lazy" for better performance
        if (!img.hasAttribute('loading')) {
            img.setAttribute('loading', 'lazy');
        }

        // Ensure images are responsive
        if (!img.classList.contains('img-fluid') && !img.style.maxWidth) {
            img.style.maxWidth = '100%';
            img.style.height = 'auto';
        }
    });
}

/**
 * Adjust font sizes based on screen size
 */
function adjustFontSizes() {
    if (window.innerWidth <= 400) {
        document.body.style.fontSize = '14px';
    } else if (window.innerWidth <= 600) {
        document.body.style.fontSize = '15px';
    } else {
        document.body.style.fontSize = '';
    }
}

/**
 * Handle orientation changes
 */
function adjustForOrientation() {
    // Recalculate viewport height for mobile browsers
    const vh = window.innerHeight * 0.01;
    document.documentElement.style.setProperty('--vh', `${vh}px`);

    // Adjust hero section height on orientation change
    const heroSection = document.querySelector('.hero-section');
    if (heroSection && window.innerWidth <= 900) {
        if (window.orientation === 90 || window.orientation === -90) {
            // Landscape
            heroSection.style.minHeight = 'auto';
        } else {
            // Portrait
            heroSection.style.minHeight = '100vh';
        }
    }
}

/**
 * Adjust layout for different screen sizes
 */
function adjustForScreenSize() {
    adjustFontSizes();

    // Adjust image preview sizes
    const imagePreviews = document.querySelectorAll('.image-preview img');
    imagePreviews.forEach(function(img) {
        const maxHeight = window.innerWidth <= 600 ? '150px' : '200px';
        img.style.maxHeight = maxHeight;
    });

    // Close mobile menu if screen becomes large
    if (window.innerWidth > 600) {
        const navbar = document.getElementById('main-navbar');
        const menuOverlay = document.getElementById('menuOverlay');
        const menuToggle = document.getElementById('menuToggle');

        if (navbar && navbar.classList.contains('active')) {
            navbar.classList.remove('active');
            if (menuOverlay) {
                menuOverlay.classList.remove('active');
            }
            if (menuToggle) {
                menuToggle.setAttribute('aria-expanded', 'false');
                const icon = menuToggle.querySelector('i');
                if (icon) {
                    icon.className = 'fas fa-bars';
                }
            }
            document.body.style.overflow = '';
        }
    }
}

/**
 * Format a number with commas as thousands separators
 * @param {number} num - The number to format
 * @returns {string} - Formatted number
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ",");
}

/**
 * Scroll to an element smoothly
 * @param {string} elementId - ID of the element to scroll to
 */
function scrollToElement(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}
