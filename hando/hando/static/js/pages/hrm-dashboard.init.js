/*
Template Name: Hando - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: dashboard init Js
*/

var options = {
  series: [
    {
      name: "Financial team",
      data: [30, 28, 56, 44, 35, 30, 40],
    },
    {
      name: "Project Manager",
      data: [45, 39, 40, 34, 47, 40, 42],
    },
    {
      name: "Marketing  team",
      data: [49, 56, 50, 24, 45, 28, 38],
    },
    {
      name: "Product Design team",
      data: [39, 30, 38, 42, 25, 42, 55],
    },
  ],
  chart: {
    type: "bar",
    height: 255,
    stacked: true,
    parentHeightOffset: 0,
    toolbar: {
      show: false,
    },
  },
  grid: {
    borderColor: "#f1f1f1",
    strokeDashArray: 3,
    show: false,
  },

  plotOptions: {
    bar: {
      columnWidth: "60%",
      borderRadius: 2,
      isFunnel3d: true,
    },
  },
  responsive: [
    {
      breakpoint: 480,
      options: {
        chart: {
          width: "100%",
        },
        legend: {
          position: "bottom",
        },
      },
    },
  ],
  colors: ["#0055fb", "#108dff", "#87DAE9", "#D0F2FB"],
  dataLabels: {
    enabled: false,
  },
  stroke: {
    show: true,
    width: 2,
    colors: ["transparent"],
  },
  xaxis: {
    categories: ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul"],
  },
  yaxis: {
    show: false,
  },
  fill: {
    opacity: 1,
  },
  legend: {
    show: true,
    position: "top",

    fontWeight: 500,
    horizontalAlign: "left",
    itemMargin: {
      horizontal: 10,
      vertical: 0,
    },
  },
};
var chart = new ApexCharts(document.querySelector("#job-report"), options);
chart.render();

// Job Summary
var options = {
  series: [20, 25, 55, 35], // Values for the segments
  chart: {
    type: "donut",
    height: 212,
  },
  labels: ["Active Job", "Unactive", "Closed", "On Hold"], // Customize as needed
  colors: [
    "#108dff",
    "rgba(16, 141, 255, 0.7)",
    "rgba(16, 141, 255, 0.5)",
    "rgba(16, 141, 255, 0.2)",
  ], // Custom segment colors
  plotOptions: {
    pie: {
      donut: {
        size: "70%",
        labels: {
          show: true,
          total: {
            show: true,
            label: "Total Jobs",
            formatter: () => "134",
          },
        },
      },
    },
  },
  stroke: {
    width: 0,
  },
  dataLabels: {
    enabled: false,
  },
  legend: {
    show: false,
  },
};
var chart = new ApexCharts(
  document.querySelector("#your-preformance"),
  options
);
chart.render();

//  Income Statistics
var options = {
  series: [
    {
      name: "Income",
      data: [
        6800, 6800, 8800, 8800, 10200, 10200, 8600, 8600, 7200, 8000, 11000,
        11000,
      ],
    },
    {
      name: "Expense",
      data: [
        2500, 2500, 4500, 3200, 3200, 2000, 4500, 4500, 2500, 2500, 5000, 5000,
      ],
    },
  ],
  chart: {
    type: "line",
    height: 292,
    parentHeightOffset: 0,
    toolbar: {
      show: false,
    },
  },
  stroke: {
    curve: "smooth",
    width: 2,
  },
  colors: ["#108dff", "#E77636"],
  fill: {
    type: "gradient",
  },
  xaxis: {
    categories: [
      "Jan",
      "Feb",
      "Mar",
      "Apr",
      "May",
      "Jun",
      "Jul",
      "Aug",
      "Sep",
      "Oct",
      "Nov",
      "Dec",
    ],
  },
  yaxis: {
    min: 0,
    labels: {
      formatter: (value) => `$${(value / 1000).toFixed(0)}k`,
    },
  },
  tooltip: {
    shared: true,
    intersect: false,
    theme: "light",
    marker: {
      show: true,
    },
    y: {
      formatter: (value) => `$${value.toLocaleString()}`,
    },
  },
  grid: {
    borderColor: "#f0f4f7",
    xaxis: {
      lines: {
        show: true,
      },
    },
    yaxis: {
      lines: {
        show: true,
      },
    },
  },
};
var chart = new ApexCharts(document.querySelector("#staff-work"), options);
chart.render();
