/*
Template Name: Hando - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: dashboard init Js
*/

// Website Traffic
var options = {
  series: [
    {
      name: "Desktops",
      data: [35, 78, 40, 90, 56, 80, 15],
    },
  ],
  chart: {
    height: 45,
    type: "area",
    sparkline: {
      enabled: true,
    },
    animations: {
      enabled: false,
    },
    dropShadow: {
      enabled: true,
      top: 10,
      left: 0,
      bottom: 10,
      blur: 2,
      color: "#f0f4f7",
      opacity: 0.3,
    },
  },
  colors: ["#c26316"],
  fill: {
    type: "gradient",
    gradient: {
      shadeIntensity: 1,
      opacityFrom: 0.5,
      opacityTo: 0.1,
      stops: [0, 90, 100],
    },
  },
  tooltip: {
    enabled: false,
  },
  dataLabels: {
    enabled: false,
  },
  grid: {
    show: false,
  },
  xaxis: {
    labels: {
      show: false,
    },
    axisBorder: {
      show: false,
    },
    axisTicks: {
      show: false,
    },
  },
  yaxis: {
    show: false,
  },
  stroke: {
    curve: "smooth",
    width: 2,
  },
};
var chartOne = new ApexCharts(
  document.querySelector("#website-traffic"),
  options
);
chartOne.render();

// Conversion Chart
var options = {
  series: [
    {
      name: "Desktops",
      data: [25, 55, 20, 60, 35, 60, 15],
    },
  ],
  chart: {
    height: 45,
    type: "area",
    sparkline: {
      enabled: true,
    },
    animations: {
      enabled: false,
    },
    dropShadow: {
      enabled: true,
      top: 10,
      left: 0,
      bottom: 10,
      blur: 2,
      color: "#f0f4f7",
      opacity: 0.3,
    },
  },
  colors: ["#E7366B"],
  fill: {
    type: "gradient",
    gradient: {
      shadeIntensity: 1,
      opacityFrom: 0.5,
      opacityTo: 0.1,
      stops: [0, 90, 100],
    },
  },
  tooltip: {
    enabled: false,
  },
  dataLabels: {
    enabled: false,
  },
  grid: {
    show: false,
  },
  xaxis: {
    labels: {
      show: false,
    },
    axisBorder: {
      show: false,
    },
    axisTicks: {
      show: false,
    },
  },
  yaxis: {
    show: false,
  },
  stroke: {
    curve: "smooth",
    width: 2,
  },
};
var chartOne = new ApexCharts(
  document.querySelector("#conversion-visitors"),
  options
);
chartOne.render();

// Session Duration Chart
var options = {
  series: [
    {
      name: "Desktops",
      data: [25, 68, 2, 50, 25, 55, 89],
    },
  ],
  chart: {
    height: 45,
    type: "area",
    sparkline: {
      enabled: true,
    },
    animations: {
      enabled: false,
    },
    dropShadow: {
      enabled: true,
      top: 10,
      left: 0,
      bottom: 10,
      blur: 2,
      color: "#f0f4f7",
      opacity: 0.3,
    },
  },
  colors: ["#287F71"],
  fill: {
    type: "gradient",
    gradient: {
      shadeIntensity: 1,
      opacityFrom: 0.5,
      opacityTo: 0.1,
      stops: [0, 90, 100],
    },
  },
  tooltip: {
    enabled: false,
  },
  dataLabels: {
    enabled: false,
  },
  grid: {
    show: false,
  },
  xaxis: {
    labels: {
      show: false,
    },
    axisBorder: {
      show: false,
    },
    axisTicks: {
      show: false,
    },
  },
  yaxis: {
    show: false,
  },
  stroke: {
    curve: "smooth",
    width: 2,
  },
};
var chartOne = new ApexCharts(
  document.querySelector("#session-duration"),
  options
);
chartOne.render();

// Active Users
var options = {
  series: [
    {
      name: "Desktops",
      data: [36, 78, 36, 58, 35, 65, 55],
    },
  ],
  chart: {
    height: 45,
    type: "area",
    sparkline: {
      enabled: true,
    },
    animations: {
      enabled: false,
    },
    dropShadow: {
      enabled: true,
      top: 10,
      left: 0,
      bottom: 10,
      blur: 2,
      color: "#f0f4f7",
      opacity: 0.3,
    },
  },
  colors: ["#108dff"],
  fill: {
    type: "gradient",
    gradient: {
      shadeIntensity: 1,
      opacityFrom: 0.5,
      opacityTo: 0.1,
      stops: [0, 90, 100],
    },
  },
  tooltip: {
    enabled: false,
  },
  dataLabels: {
    enabled: false,
  },
  grid: {
    show: false,
  },
  xaxis: {
    labels: {
      show: false,
    },
    axisBorder: {
      show: false,
    },
    axisTicks: {
      show: false,
    },
  },
  yaxis: {
    show: false,
  },
  stroke: {
    curve: "smooth",
    width: 2,
  },
};
var chartOne = new ApexCharts(document.querySelector("#active-users"), options);
chartOne.render();

// Earning Reports
var options = {
  series: [
    {
      name: "Total Income",
      type: "bar",
      data: [34, 65, 46, 68, 49, 61, 42, 44, 78, 52, 63, 67],
    },
    {
      name: "Total Expense",
      type: "bar",
      data: [16, 20, 32, 38, 42, 25, 15, 21, 17, 29, 12, 35],
    },
    {
      name: "Total Revenue",
      type: "line",
      data: [12, 16, 28, 32, 38, 22, 10, 18, 14, 58, 24, 70],
    },
  ],
  chart: {
    height: 340,
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
  colors: ["#108dff", "#963b68", "#287F71"],
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
var chart = new ApexCharts(document.querySelector("#monthly-sales"), options);
chart.render();

// Total Leads
var options = {
  series: [
    {
      name: "Created",
      data: [48, 32, 42, 28, 15, 32, 20],
    },
    {
      name: "Converted",
      data: [32, 33, 39, 42, 72, 55, 60],
    },
  ],
  chart: {
    type: "bar",
    height: 367,
    stacked: true,
    foreColor: "#adb0bb",
    parentHeightOffset: 0,
    toolbar: {
      show: false,
    },
  },
  plotOptions: {
    bar: {
      horizontal: false,
      columnWidth: "20%",
      endingShape: "rounded",
      startingShape: "rounded",
    },
  },
  dataLabels: {
    enabled: false,
  },
  xaxis: {
    categories: ["Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug"],
  },
  grid: {
    borderColor: "rgba(0,0,0,0.1)",
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
  },
  colors: ["#c26316", "#D49664"],
  legend: {
    position: "bottom",
  },
  fill: {
    opacity: 1,
  },
};
var chart = new ApexCharts(document.querySelector("#totalleads"), options);
chart.render();

// Top Session
var options = {
  series: [65.48, 112.02, 80.48, 58.65],
  labels: ["Chrome", "Firefox", "Safari", "Opera"],
  chart: {
    type: "donut",
    height: 235,
  },
  plotOptions: {
    pie: {
      size: 100,
      donut: {
        size: "80%",
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
    width: 0,
  },
  yaxis: {
    labels: {
      formatter: function (e) {
        return e + "k Session";
      },
    },
    tickAmount: 4,
    min: 0,
  },
  colors: ["#287F71", "#522c8f", "#E77636", "#01D4FF"],
};
var chart = new ApexCharts(document.querySelector("#top-session"), options);
chart.render();
