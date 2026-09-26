/**
 * Chart.js Analytics Controller.
 * Renders crime category breakdowns and payment channel distributions
 * optimized for the professional light operational theme.
 */

let categoryChartInstance = null;
let channelChartInstance = null;

export const ChartController = {
  renderCharts(statsData) {
    this.renderCategoryChart(statsData.crime_category_breakdown || {});
    this.renderChannelChart(statsData.payment_channel_breakdown || {});
  },

  renderCategoryChart(categoryData) {
    const canvas = document.getElementById("categoryChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (categoryChartInstance) {
      categoryChartInstance.destroy();
    }

    const labels = Object.keys(categoryData).map(k => k.replace(/_/g, " "));
    const counts = Object.values(categoryData);

    categoryChartInstance = new Chart(ctx, {
      type: "doughnut",
      data: {
        labels: labels,
        datasets: [
          {
            data: counts,
            backgroundColor: [
              "#0d9488", // Restrained Teal
              "#0891b2", // Cyan
              "#10b981", // Emerald
              "#d97706", // Amber
              "#dc2626", // Red
            ],
            borderColor: "#ffffff",
            borderWidth: 2,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: {
            position: "bottom",
            labels: {
              color: "#475569",
              font: { size: 10, weight: 600 },
              boxWidth: 12,
              padding: 8,
            },
          },
        },
        cutout: "68%",
      },
    });
  },

  renderChannelChart(channelData) {
    const canvas = document.getElementById("channelChart");
    if (!canvas) return;

    const ctx = canvas.getContext("2d");
    if (channelChartInstance) {
      channelChartInstance.destroy();
    }

    const labels = Object.keys(channelData);
    const counts = Object.values(channelData);

    channelChartInstance = new Chart(ctx, {
      type: "bar",
      data: {
        labels: labels,
        datasets: [
          {
            label: "Incident Volume",
            data: counts,
            backgroundColor: "#0d9488", // Restrained Teal accent
            borderRadius: 4,
          },
        ],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        plugins: {
          legend: { display: false },
        },
        scales: {
          x: {
            ticks: { color: "#475569", font: { size: 11, weight: 600 } },
            grid: { display: false },
          },
          y: {
            ticks: { color: "#475569", font: { size: 10 } },
            grid: { color: "#f1f5f9" },
          },
        },
      },
    });
  },
};
