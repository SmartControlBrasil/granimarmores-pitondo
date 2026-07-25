/*
Template Name: Hando - Responsive Bootstrap 5 Admin Dashboard
Author: Zoyothemes
Version: 1.0.0
Website: https://zoyothemes.com/
File: CRM dashboard init Js
*/

// sale Overview
var options = {
  series: [
    {
      name: "Total Income",
      data: [
        1000, 2100, 1800, 4540, 4540, 2300, 2300, 6860, 6860, 3500, 3500, 2100,
      ],
    },
    {
      name: "Total Revenue",
      data: [
        2000, 5300, 1100, 1300, 4800, 5200, 7800, 4350, 4750, 7380, 4540, 4800,
      ],
    },
    {
      name: "Total Revenue",
      data: [
        7400, 5900, 3200, 7300, 3400, 5800, 8900, 6540, 4100, 6380, 2300, 6750,
      ],
    },
  ],
  chart: {
    type: "area",
    height: 300,
    parentHeightOffset: 0,
    toolbar: {
      show: false,
    },
    dropShadow: {
      enabled: false,
      enabledOnSeries: undefined,
      top: 0,
      left: 0,
      blur: 4,
      color: "#000",
      opacity: 0.3,
    },
  },
  dataLabels: {
    enabled: false,
  },
  colors: ["#108dff", "#E77636", "#db398a"],
  fill: {
    opacity: 1,
    type: "gradient",
    gradient: {
      shadeIntensity: 1,
      opacityFrom: 0.4,
      opacityTo: 0.1,
      stops: [0, 90, 100],
      colorStops: [
        [
          {
            offset: 0,
            color: "#108dff",
            opacity: 0.3,
          },
          {
            offset: 50,
            color: "#108dff",
            opacity: 0.2,
          },
          {
            offset: 100,
            color: "#108dff",
            opacity: 0.0,
          },
        ],
        [
          {
            offset: 0,
            color: "#E77636",
            opacity: 0.3,
          },
          {
            offset: 50,
            color: "#E77636",
            opacity: 0.2,
          },
          {
            offset: 100,
            color: "#E77636",
            opacity: 0.0,
          },
        ],
        [
          {
            offset: 0,
            color: "#db398a",
            opacity: 0.08,
          },
          {
            offset: 50,
            color: "#db398a",
            opacity: 0.06,
          },
          {
            offset: 100,
            color: "#db398a",
            opacity: 0.0,
          },
        ],
      ],
    },
  },
  stroke: {
    curve: ["smooth", "smooth", "smooth"],
    width: [2, 0, 2],
  },
  grid: {
    strokeDashArray: 3,
    xaxis: {
      lines: {
        show: true,
      },
    },
    yaxis: {
      lines: {
        show: false,
      },
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
  },
  yaxis: {
    min: 0,
    labels: {
      formatter: (value) => `$${(value / 1000).toFixed(0)}k`,
    },
  },
  legend: {
    position: "bottom",
  },
};
var chart = new ApexCharts(document.querySelector("#sales-overview"), options);
chart.render();

// Sales Pipeline
var options = {
  series: [65.48, 112.02, 80.48],
  labels: ["Won", "Discovery", "Undiscovery"],
  chart: {
    type: "donut",
    height: 200,
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
  colors: ["#287F71", "#522c8f", "#E77636"],
};
var chart = new ApexCharts(document.querySelector("#top-session"), options);
chart.render();

// Recent order
var options = {
  chart: {
    height: 307,
    type: "radialBar",
  },
  plotOptions: {
    radialBar: {
      startAngle: -135,
      endAngle: 135,
      dataLabels: {
        name: {
          fontSize: "13px",
          color: undefined,
          offsetY: 25,
        },
        value: {
          offsetY: -15,
          fontSize: "25px",
          color: "#343a40",
          formatter: function (val) {
            return val + "%";
          },
        },
      },
    },
  },
  fill: {
    gradient: {
      enabled: true,
      shade: "dark",
      shadeIntensity: 0.2,
      inverseColors: false,
      opacityFrom: 1,
      opacityTo: 1,
      stops: [0, 50, 65, 91],
    },
  },
  stroke: {
    dashArray: 7,
  },
  colors: ["#E77636"],
  series: [87],
  labels: ["Growth"],
};
var chart = new ApexCharts(document.querySelector("#browservisiting"), options);
chart.render();

// Deals Statistics
var options = {
  series: [
    {
      name: "Hot Leads",
      data: [80, 50, 30, 40, 100, 20],
    },
    {
      name: "Normal Leads",
      data: [20, 100, 35, 78, 60, 30],
    },
    {
      name: "Cold Leads",
      data: [20, 30, 40, 80, 20, 80],
    },
    {
      name: "Qualified",
      data: [44, 76, 78, 13, 43, 10],
    },
  ],
  chart: {
    type: "radar",
    height: 323,
    parentHeightOffset: 0,
    toolbar: {
      show: false,
    },
  },
  stroke: {
    width: 1,
  },
  fill: {
    opacity: 0.1,
  },
  markers: {
    size: 3,
    hover: {
      size: 4,
    },
  },
  tooltip: {
    y: {
      formatter: function (val) {
        return val;
      },
    },
  },
  legend: {
    show: true,
    markers: {
      width: 6,
      height: 6,
      strokeWidth: 0,
      strokeColor: "#fff",
      fillColors: undefined,
      radius: 5,
      customHTML: undefined,
      onClick: undefined,
      offsetX: 0,
      offsetY: 0,
    },
  },
  xaxis: {
    categories: ["2019", "2020", "2021", "2022", "2023", "2024"],
    axisBorder: { show: false },
    labels: {
      show: true,
      style: {
        colors: [
          "#001b2f",
          "#001b2f",
          "#001b2f",
          "#001b2f",
          "#001b2f",
          "#001b2f",
        ],
        fontSize: "13px",
      },
    },
  },
  yaxis: {
    stepSize: 20,
  },
  colors: ["#108dff", "#963b68", "#E77636", "#27ebb0"],
  dataLabels: {
    enabled: false,
    background: {
      enabled: true,
    },
  },
};
var chart = new ApexCharts(
  document.querySelector("#deals-statistics"),
  options
);
chart.render();
