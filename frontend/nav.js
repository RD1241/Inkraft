// nav.js — Shared hamburger navigation module
// Import and call initNav() on each page

export function initNav() {
  const hamburgerBtn = document.getElementById('hamburger-btn');
  const headerNav    = document.querySelector('.header-nav');
  
  if (!hamburgerBtn || !headerNav) return;
  
  // Create backdrop
  const backdrop = document.createElement('div');
  backdrop.className = 'nav-backdrop';
  document.body.appendChild(backdrop);
  
  function openNav() {
    headerNav.classList.add('open');
    hamburgerBtn.classList.add('open');
    hamburgerBtn.setAttribute('aria-expanded', 'true');
    backdrop.classList.add('active');
    document.body.style.overflow = 'hidden'; // prevent scroll behind drawer
  }
  
  function closeNav() {
    headerNav.classList.remove('open');
    hamburgerBtn.classList.remove('open');
    hamburgerBtn.setAttribute('aria-expanded', 'false');
    backdrop.classList.remove('active');
    document.body.style.overflow = '';
  }
  
  hamburgerBtn.addEventListener('click', (e) => {
    e.stopPropagation();
    if (headerNav.classList.contains('open')) {
      closeNav();
    } else {
      openNav();
    }
  });
  
  backdrop.addEventListener('click', closeNav);
  
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && headerNav.classList.contains('open')) {
      closeNav();
    }
  });
  
  // Close on nav link click (mobile)
  headerNav.querySelectorAll('.nav-link').forEach(link => {
    link.addEventListener('click', closeNav);
  });
}
