/**
 * Chart.js Analytics Controller.
 * Renders crime category breakdowns and payment channel distributions.
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
              "#38bdf8", // Sky blue
              "#06b6d4", // Cyan
              "#10b981", // Emerald
              "#f59e0b", // Amber
              "#ef4444", // Red
            ],
            borderColor: "#111827",
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
              color: "#94a3b8",
              font: { size: 10, weight: 600 },
              boxWidth: 12,
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
            backgroundColor: "#0284c7",
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
            ticks: { color: "#94a3b8", font: { size: 11, weight: 600 } },
            grid: { display: false },
          },
          y: {
            ticks: { color: "#94a3b8", font: { size: 10 } },
            grid: { color: "rgba(51, 65, 85, 0.4)" },
          },
        },
      },
    });
  },
};
