/* Light page interactivity: tabs, drag-drop visuals, score gauge. */

document.addEventListener('DOMContentLoaded', () => {
  // --- Tabs ---
  document.querySelectorAll('[data-tabs]').forEach((root) => {
    const buttons = root.querySelectorAll('.tab-btn');
    const panels = root.querySelectorAll('.tab-panel');
    buttons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const target = btn.dataset.tab;
        buttons.forEach((b) => b.classList.toggle('active', b === btn));
        panels.forEach((p) => p.classList.toggle('active', p.dataset.tab === target));
      });
    });
  });

  // --- Drop zone visual feedback ---
  document.querySelectorAll('.drop-zone').forEach((zone) => {
    ['dragenter', 'dragover'].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.add('hover');
      })
    );
    ['dragleave', 'drop'].forEach((evt) =>
      zone.addEventListener(evt, (e) => {
        e.preventDefault();
        zone.classList.remove('hover');
      })
    );
  });

  // --- Score gauge (Chart.js) ---
  const gauge = document.getElementById('score-gauge');
  if (gauge && window.Chart) {
    const score = parseInt(gauge.dataset.score || '67', 10);
    const colors = ['#16a34a', '#f59e0b', '#dc2626'];
    const color = score >= 75 ? colors[0] : score >= 45 ? colors[1] : colors[2];
    new Chart(gauge, {
      type: 'doughnut',
      data: {
        datasets: [
          {
            data: [score, 100 - score],
            backgroundColor: [color, '#eef1f7'],
            borderWidth: 0,
            cutout: '78%',
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: true,
        plugins: { legend: { display: false }, tooltip: { enabled: false } },
        animation: { animateRotate: true, duration: 1200 },
      },
    });
  }

  // --- Filter chip toggle (visual only) ---
  document.querySelectorAll('.filters').forEach((bar) => {
    bar.querySelectorAll('.filter-chip').forEach((chip) => {
      chip.addEventListener('click', () => {
        bar.querySelectorAll('.filter-chip').forEach((c) => c.classList.remove('active'));
        chip.classList.add('active');
      });
    });
  });
});
