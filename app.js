// Mejora progresiva: la navegación y los formularios funcionan sin JavaScript.
document.querySelectorAll('form[data-confirm]').forEach((form) => {
  form.addEventListener('submit', (event) => {
    if (!window.confirm(form.dataset.confirm)) event.preventDefault();
  });
});
const error = document.querySelector('[data-error]');
if (error) error.focus();
