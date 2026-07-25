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

// Performance Overview
var options = {
  series: [
    {
      name: "Orders",
      type: "bar",
      data: [26, 59, 27, 51, 25, 39, 29, 48, 29, 52, 27, 37],
    },
    {
      name: "Sales",
      type: "line",
      data: [47, 41, 72, 35, 46, 35, 51, 78, 40, 75, 52, 58],
      // data: [47, 41, 72, 35, 46, 35, 51, 78, 61, 75, 52, 58],
    },
  ],
  chart: {
    animations: {
      enabled: false,
    },
    height: 345,
    zoom: {
      enabled: false,
    },
    toolbar: {
      show: false,
    },
  },
  plotOptions: {
    bar: {
      horizontal: false,
      columnWidth: "35%",
      endingShape: "rounded",
      borderRadius: 6,
    },
  },
  dataLabels: {
    enabled: false,
  },
  legend: {
    position: "top",
    horizontalAlign: "right",
  },
  stroke: {
    curve: "smooth",
    width: [3, 2],
  },
  grid: {
    strokeDashArray: 2,
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
  colors: ["#108dff", "#E77636"],
  xaxis: {
    type: "month",
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
    axisBorder: {
      show: true,
      color: "rgba(119, 119, 142, 0.05)",
      offsetX: 0,
      offsetY: 0,
    },
  },
};
var chart = new ApexCharts(
  document.querySelector("#performance-review"),
  options
);
chart.render();

function Earnings() {
  chart.updateOptions({
    colors: ["rgb(" + myVarVal + ")", "rgb(203,213,225)"],
  });
}

// Repeat Customer Rate
var options = {
  series: [
    {
      name: "New Customer",
      data: [85, 80, 150, 127, 220, 200, 300, 290, 314],
    },
    {
      name: "Old Customer",
      data: [215, 165, 100, 200, 145, 185, 104, 124, 82],
    },
  ],
  chart: {
    type: "line",
    height: 305,
    parentHeightOffset: 0,
    zoom: {
      enabled: false,
    },
    toolbar: {
      show: false,
    },
    animations: {
      enabled: false,
    },
  },
  dataLabels: {
    enabled: false,
  },
  fill: {
    opacity: 1,
  },
  stroke: {
    width: [2, 2],
    curve: "straight",
    dashArray: [0, 7],
  },
  legend: {
    position: "top",
    horizontalAlign: "right",
    tooltipHoverFormatter: function (val, opts) {
      return (
        val +
        " <strong>" +
        opts.w.globals.series[opts.seriesIndex][opts.dataPointIndex] +
        "</strong>"
      );
    },
  },
  markers: {
    size: 0,
    hover: {
      sizeOffset: 6,
    },
  },
  grid: {
    strokeDashArray: 2,
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
  xaxis: {
    labels: {
      padding: 0,
    },
    axisBorder: {
      show: false,
    },
    tooltip: {
      enabled: false,
    },
    categories: ["09", "10", "11", "12", "13", "14", "15", "16"],
  },
  tooltip: {
    y: [
      {
        title: {
          formatter: function (val) {
            return val;
          },
        },
      },
      {
        title: {
          formatter: function (val) {
            return val;
          },
        },
      },
    ],
  },
  colors: ["#108dff", "#27ebb0"],
};
var chart = new ApexCharts(document.querySelector("#repeat-customer"), options);
chart.render();

// Orders Report Chart
var options = {
  chart: {
    height: 264,
    type: "radialBar",
    responsive: "true",
    offsetX: 0,
    offsetY: 15,
  },
  plotOptions: {
    radialBar: {
      startAngle: -135,
      endAngle: 135,
      size: 120,
      imageWidth: 50,
      imageHeight: 50,
      track: {
        strokeWidth: "97%",
      },
      dropShadow: {
        enabled: false,
        top: 0,
        left: 0,
        bottom: 0,
        blur: 3,
        opacity: 0.5,
      },
      dataLabels: {
        name: {
          fontSize: "16px",
          color: undefined,
          offsetY: 30,
        },
        hollow: {
          size: "60%",
        },
        value: {
          offsetY: -10,
          fontSize: "22px",
          color: undefined,
          formatter: function (val) {
            return val + "%";
          },
        },
      },
    },
  },
  colors: ["#108dff"],
  fill: {
    type: "solid",
    gradient: {
      shade: "dark",
      type: "horizontal",
      shadeIntensity: 0.5,
      gradientToColors: ["#108dff"],
      inverseColors: false,
      opacityFrom: 1,
      opacityTo: 1,
      stops: [0, 100],
    },
  },
  stroke: {
    dashArray: 3,
  },
  series: [92],
  labels: ["Orders"],
};
var chart = new ApexCharts(document.querySelector("#ordersreport"), options);
chart.render();

// Contry Map
class VectorMap {
  initWorldCountryMap() {
    const map = new jsVectorMap({
      map: "world_merc",
      selector: "#world-country",
      zoomOnScroll: false,
      zoomButtons: false,
      selectedMarkers: [0, 2],
      markersSelectable: true,
      markers: [
        { name: "Palestine", coords: [31.9474, 35.2272] },
        { name: "Russia", coords: [61.524, 105.3188] },
        { name: "Canada", coords: [56.1304, -106.3468] },
        { name: "Greenland", coords: [71.7069, -42.6043] },
      ],
      regionStyle: {
        initial: {
          stroke: "#4a5a6b",
          fill: "#ced4da",
          strokeWidth: 0.25,
          fillOpacity: 1,
        },
      },
      markerStyle: {
        initial: { fill: "#108dff" },
        selected: { fill: "#4a5a6b" },
      },
      labels: {
        markers: {
          render: (marker) => marker.name,
        },
      },
    });
  }

  init() {
    this.initWorldCountryMap();
  }
}

document.addEventListener("DOMContentLoaded", function (e) {
  new VectorMap().init();
});
