/*
Template Name: Hando - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: dashboard init Js
*/

// =================================================
// New Order
// =================================================

var options = {
  series: [
    {
      name: "Active Job",
      data: [44, 55, 41, 67, 22, 43, 44, 55, 41, 67, 22, 43],
    },
    {
      name: "On Hold",
      data: [13, 23, 20, 8, 13, 27, 13, 23, 20, 8, 13, 27],
    },
    {
      name: "Shortlisted",
      data: [11, 17, 15, 15, 21, 14, 11, 17, 15, 15, 21, 14],
    },
  ],
  chart: {
    type: "bar",
    height: 360,
    stacked: true,
    // foreColor: "#adb0bb",
    parentHeightOffset: 0,
    toolbar: {
      show: false,
    },
  },
  grid: {
    borderColor: "#f1f1f1",
    strokeDashArray: 3,
  },
  plotOptions: {
    bar: {
      columnWidth: "40%",
      borderRadius: 2,
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
  colors: ["#108dff", "rgba(16, 141, 255, 0.5)", "rgba(16, 141, 255, 0.2)"],
  dataLabels: {
    enabled: false,
  },
  stroke: {
    show: true,
    width: 2,
    colors: ["transparent"],
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
  fill: {
    opacity: 1,
  },
  legend: {
    show: true,
    position: "top",
    horizontalAlign: "right",
  },
};

var chart = new ApexCharts(document.querySelector("#job-report"), options);
chart.render();

var options = {
  series: [75, 55, 65, 85],
  labels: ["36%", "10%", "36%", "12%"],
  chart: {
    type: "radialBar",
    height: 209,
    fontFamily: "inherit",
    foreColor: "#c6d1e9",
  },
  plotOptions: {
    radialBar: {
      inverseOrder: false,
      startAngle: 0,
      endAngle: 270,
      hollow: {
        margin: 1,
        size: "40%",
      },
      dataLabels: {
        show: false,
      },
    },
  },
  legend: {
    show: false,
  },
  stroke: { width: 1, lineCap: "round" },
  tooltip: {
    enabled: false,
    fillSeriesColor: false,
  },
  colors: ["#108dff", "#963b68", "#287F71", "#01D4FF"],
};

var chart = new ApexCharts(document.querySelector("#sales-overview"), options);
chart.render();
