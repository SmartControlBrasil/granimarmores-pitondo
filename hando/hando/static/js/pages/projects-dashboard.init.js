/*
Template Name: Hando - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: dashboard init Js
*/

// =================================================
// Project Statistics
// =================================================
var options = {
  series: [65.48, 112.02, 80.48, 58.65],
  labels: ["Chrome", "Firefox", "Safari", "Opera"],
  chart: {
    type: "donut",
    height: 200,
  },
  plotOptions: {
    pie: {
      donut: {
        size: "60%",
      },
    },
  },
  dataLabels: {
    enabled: false,
  },
  legend: {
    show: false,
  },
  stroke: {
    show: true,
    width: 0,
    colors: ["transparent"],
  },
  tooltip: {
    y: {
      formatter: function (o) {
        return o + " %";
      },
    },
  },
  colors: ["#287F71", "#522c8f", "#E77636", "#01D4FF"],
};
var chart = new ApexCharts(
  document.querySelector("#project-categories"),
  options
);
chart.render();

// Project Statistics
var options = {
  series: [
    {
      name: "Active Projects",
      type: "bar",
      data: [100, 100, 120, 148, 120, 120, 220, 103, 83, 114, 265, 174],
    },
    {
      name: "Completed Projects",
      type: "bar",
      data: [95, 80, 130, 115, 190, 115, 159, 102, 138, 136, 62, 240],
    },
    // {
    //   name: "Total Revenue",
    //   type: "line",
    //   data: [12, 16, 28, 32, 38, 22, 10, 18, 14, 58, 24, 70],
    // },
  ],
  chart: {
    height: 312,
    type: "line",
    toolbar: {
      show: false,
    },
  },
  stroke: {
    dashArray: [0, 0],
    width: [0, 0, 2],
    curve: "smooth",
  },
  fill: {
    opacity: [1, 1],
    type: ["solid", "solid"],
    gradient: {
      type: "horizontal",
      inverseColors: false,
      opacityFrom: 0.5,
      opacityTo: 0,
      stops: [0, 90],
    },
  },
  markers: {
    size: [0, 0],
    strokeWidth: 2,
    hover: {
      size: 4,
    },
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
    axisTicks: {
      show: false,
    },
    axisBorder: {
      show: false,
    },
  },
  yaxis: {
    min: 0,
    axisBorder: {
      show: false,
    },
  },
  grid: {
    show: true,
    strokeDashArray: 3,
    xaxis: {
      lines: {
        show: false,
      },
    },
    yaxis: {
      lines: {
        show: true,
      },
    },
    padding: {
      top: 0,
      right: -2,
      bottom: 0,
      left: 10,
    },
  },
  legend: {
    show: true,
    horizontalAlign: "center",
    offsetX: 0,
    offsetY: 5,
    markers: {
      width: 9,
      height: 9,
      radius: 6,
    },
    itemMargin: {
      horizontal: 10,
      vertical: 0,
    },
  },
  plotOptions: {
    bar: {
      columnWidth: "50%",
      barHeight: "70%",
      borderRadius: 3,
    },
  },
  colors: ["#108dff", "rgba(16, 141, 255, 0.3)"],
  tooltip: {
    shared: true,
    y: [
      {
        formatter: function (y) {
          if (typeof y !== "undefined") {
            return y.toFixed(1) + "k";
          }
          return y;
        },
      },
      {
        formatter: function (y) {
          if (typeof y !== "undefined") {
            return y.toFixed(1) + "k";
          }
          return y;
        },
      },
      {
        formatter: function (y) {
          if (typeof y !== "undefined") {
            return y.toFixed(1) + "k";
          }
          return y;
        },
      },
    ],
  },
};
var chart = new ApexCharts(
  document.querySelector("#project-statistics"),
  options
);
chart.render();

// Project Budget

var options = {
  series: [
    {
      name: "Inprogress",
      data: [
        20000, 20000, 15000, 15000, 30000, 30000, 45000, 45000, 30000, 10000,
        32000, 32000,
      ],
    },
    {
      name: "Progress",
      data: [
        30000, 30000, 22000, 22000, 15000, 15000, 15000, 28000, 28000, 38000,
        28000, 28000,
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
    max: 50000,
    tickAmount: 5,
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
var chart = new ApexCharts(document.querySelector("#project_budget"), options);
chart.render();
