/**
 * Active Section Tracker
 * Detects which section the user is currently scrolling through and updates both sidebars
 */

function initializeScrollTracking() {
  // Get all sections with IDs (these are the trackable sections)
  const sections = document.querySelectorAll('.doc-section[id], .doc-content > section[id]');
  const sidebarLinks = document.querySelectorAll('.sidebar-link');
  const otpLinks = document.querySelectorAll('.otp-link');
  
  if (sections.length === 0) return;

  // Create a map of section IDs to elements for quick lookup
  const sectionMap = {};
  sections.forEach(section => {
    sectionMap[section.id] = section;
  });

  function updateActiveLinks() {
    // Find the section currently in view
    let currentSection = null;
    let minDistance = Infinity;

    sections.forEach(section => {
      const rect = section.getBoundingClientRect();
      // Find the section whose top is closest to the top of the viewport
      // but not below it (or just slightly below)
      const distance = Math.abs(rect.top - 100); // 100px offset for fixed header
      
      if (rect.top <= 150 && distance < minDistance) {
        minDistance = distance;
        currentSection = section.id;
      }
    });

    // If no section found above viewport, use the first one that's partially visible
    if (!currentSection) {
      sections.forEach(section => {
        const rect = section.getBoundingClientRect();
        if (rect.bottom > 0 && rect.top < window.innerHeight) {
          if (!currentSection || rect.top < document.querySelector(`#${currentSection}`)?.getBoundingClientRect().top) {
            currentSection = section.id;
          }
        }
      });
    }

    if (!currentSection) {
      currentSection = sections[0].id;
    }

    // Update sidebar links
    sidebarLinks.forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('href').includes(`#${currentSection}`)) {
        link.classList.add('active');
      }
    });

    // Update right sidebar (on this page) links
    otpLinks.forEach(link => {
      link.classList.remove('active');
      if (link.getAttribute('href').includes(`#${currentSection}`)) {
        link.classList.add('active');
      }
    });
  }

  // Listen to scroll events with debouncing
  let scrollTimeout;
  window.addEventListener('scroll', () => {
    clearTimeout(scrollTimeout);
    scrollTimeout = setTimeout(updateActiveLinks, 50);
  }, { passive: true });

  // Also update on initial load
  updateActiveLinks();

  // Update on window resize (in case layout changes)
  window.addEventListener('resize', updateActiveLinks);

  // Handle direct clicks on anchor links
  document.querySelectorAll('a[href*="#"]').forEach(link => {
    link.addEventListener('click', () => {
      setTimeout(updateActiveLinks, 100);
    });
  });
}

// Initialize when DOM is ready
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeScrollTracking);
} else {
  initializeScrollTracking();
}

/**
 * Copy to clipboard functionality for code blocks
 */
function initializeCopyButtons() {
  const copyButtons = document.querySelectorAll('.copy-btn');
  
  copyButtons.forEach(button => {
    button.addEventListener('click', () => {
      const codeBlock = button.closest('.code-block');
      const codeContent = codeBlock.querySelector('.code-inner');
      const text = codeContent.textContent;

      navigator.clipboard.writeText(text).then(() => {
        // Visual feedback
        const originalText = button.textContent;
        button.textContent = '✓ copied';
        setTimeout(() => {
          button.textContent = originalText;
        }, 2000);
      }).catch(err => {
        console.error('Failed to copy:', err);
      });
    });
  });
}

// Initialize copy buttons
if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initializeCopyButtons);
} else {
  initializeCopyButtons();
}
