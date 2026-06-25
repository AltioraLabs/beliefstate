// Mobile menu toggle logic for beliefstate documentation
document.addEventListener('DOMContentLoaded', () => {
  const mobileToggle = document.getElementById('mobileMenuToggle');
  const mobileOverlay = document.getElementById('mobileMenuOverlay');
  
  if (mobileToggle && mobileOverlay) {
    // Toggle menu visibility
    mobileToggle.addEventListener('click', () => {
      const isActive = mobileToggle.classList.toggle('active');
      mobileOverlay.classList.toggle('active');
      document.body.classList.toggle('no-scroll', isActive);
    });

    // Close mobile menu when clicking any link
    mobileOverlay.querySelectorAll('a').forEach(link => {
      link.addEventListener('click', () => {
        mobileToggle.classList.remove('active');
        mobileOverlay.classList.remove('active');
        document.body.classList.remove('no-scroll');
      });
    });

    // Support ESC key to close the mobile menu
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && mobileOverlay.classList.contains('active')) {
        mobileToggle.classList.remove('active');
        mobileOverlay.classList.remove('active');
        document.body.classList.remove('no-scroll');
      }
    });
  }

  // Close mobile menu when resizing past the tablet breakpoint (1024px)
  window.addEventListener('resize', () => {
    if (window.innerWidth > 1024) {
      if (mobileToggle) mobileToggle.classList.remove('active');
      if (mobileOverlay) mobileOverlay.classList.remove('active');
      document.body.classList.remove('no-scroll');
    }
  });

  // Active sidebar and on-this-page link highlighting via IntersectionObserver
  const headings = document.querySelectorAll('section.doc-section, h3[id]');
  const sidebarLinks = document.querySelectorAll('.sidebar-link');
  const otpLinks = document.querySelectorAll('.otp-link');

  if ('IntersectionObserver' in window && headings.length > 0) {
    const observerOptions = {
      root: null,
      rootMargin: '-80px 0px -60% 0px',
      threshold: 0
    };

    const observer = new IntersectionObserver(entries => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const id = entry.target.getAttribute('id');
          if (!id) return;

          const section = entry.target.closest('.doc-section');
          const sectionId = section ? section.getAttribute('id') : id;

          // Highlight sidebar link
          sidebarLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href) {
              try {
                const url = new URL(link.href, window.location.href);
                const isCurrentPage = url.pathname === window.location.pathname || 
                                      url.pathname.endsWith('/' + window.location.pathname.split('/').pop());
                if (isCurrentPage && url.hash === '#' + sectionId) {
                  link.classList.add('active');
                } else if (isCurrentPage) {
                  link.classList.remove('active');
                }
              } catch (e) {
                // fallback if URL parsing fails
                if (href.endsWith('#' + sectionId) || href.endsWith('/#' + sectionId)) {
                  link.classList.add('active');
                } else {
                  link.classList.remove('active');
                }
              }
            }
          });

          // Highlight on-this-page link
          otpLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (href) {
              try {
                const url = new URL(link.href, window.location.href);
                const isCurrentPage = url.pathname === window.location.pathname || 
                                      url.pathname.endsWith('/' + window.location.pathname.split('/').pop());
                if (isCurrentPage && url.hash === '#' + id) {
                  link.classList.add('active');
                } else if (isCurrentPage) {
                  link.classList.remove('active');
                }
              } catch (e) {
                // fallback if URL parsing fails
                if (href.endsWith('#' + id) || href.endsWith('/#' + id)) {
                  link.classList.add('active');
                } else {
                  link.classList.remove('active');
                }
              }
            }
          });
        }
      });
    }, observerOptions);

    headings.forEach(heading => observer.observe(heading));
  }
});
