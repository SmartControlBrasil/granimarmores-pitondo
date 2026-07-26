
(function(){
  function ready(fn){ if(document.readyState !== 'loading') fn(); else document.addEventListener('DOMContentLoaded', fn); }
  ready(function(){
    var sidebar = document.querySelector('[data-sidebar]');
    var backdrop = document.querySelector('[data-sidebar-backdrop]');
    var toggles = document.querySelectorAll('[data-sidebar-toggle]');
    function close(){ if(sidebar) sidebar.classList.remove('is-open'); if(backdrop) backdrop.classList.remove('is-open'); }
    function open(){ if(sidebar) sidebar.classList.add('is-open'); if(backdrop) backdrop.classList.add('is-open'); }
    toggles.forEach(function(btn){ btn.addEventListener('click', function(){ sidebar && sidebar.classList.contains('is-open') ? close() : open(); }); });
    if(backdrop) backdrop.addEventListener('click', close);
    document.addEventListener('keydown', function(event){ if(event.key === 'Escape') close(); });
  });
})();
