// DOM elements
const ctx = document.getElementById('myChart');
const statusDiv = document.getElementById('status');
const searchInput = document.getElementById('searchLegend');
const customLegend = document.getElementById('customLegend');
const visibleCount = document.getElementById('visibleCount');
const showAllBtn = document.getElementById('showAllBtn');
const hideAllBtn = document.getElementById('hideAllBtn');
const minDistanceSlider = document.getElementById('minDistance');
const maxDistanceSlider = document.getElementById('maxDistance');
const minDistanceLabel = document.getElementById('minDistanceLabel');
const maxDistanceLabel = document.getElementById('maxDistanceLabel');

// Global variables
let chart = null;
let allDatasets = [];
let filteredDatasets = [];
let currentSearchTerm = '';
let currentMinDistance = 0;
let currentMaxDistance = 50;

// Get filename from query parameter
const urlParams = new URLSearchParams(window.location.search);
let dataFile = urlParams.get('data');

// Load and setup dynamic navbar
function loadDynamicNavbar() {
  fetch('data/charts.json')
    .then(response => response.json())
    .then(config => {
      const navbarMenu = document.querySelector('.navbar-menu');
      navbarMenu.innerHTML = ''; // Clear existing links
      
      // Handle empty charts array
      if (!config.charts || config.charts.length === 0) {
        const message = document.createElement('div');
        message.style.color = 'rgba(255,255,255,0.7)';
        message.style.padding = '0.5rem';
        message.textContent = 'No charts available. Generate some data first.';
        navbarMenu.appendChild(message);
        
        // Set dataFile to null so chart loading will show appropriate message
        dataFile = null;
        return;
      }
      
      // Set default dataFile if not specified
      if (!dataFile) {
        const defaultChart = config.charts.find(c => c.id === config.default) || config.charts[0];
        dataFile = `data/${defaultChart.file}`;
      }
      
      config.charts.forEach(chart => {
        const link = document.createElement('a');
        link.href = `?data=data/${chart.file}`;
        link.textContent = `${chart.icon} ${chart.name}`;
        link.title = chart.description;
        
        // Add active state for current chart
        if (dataFile.includes(chart.file)) {
          link.classList.add('active');
        }
        
        navbarMenu.appendChild(link);
      });
    })
    .catch(error => {
      console.warn('Could not load charts config:', error);
      const navbarMenu = document.querySelector('.navbar-menu');
      navbarMenu.innerHTML = '<div style="color: rgba(255,255,255,0.7); padding: 0.5rem;">Charts config not available</div>';
      dataFile = null;
    });
}

// Initialize dynamic navbar and then load chart
loadDynamicNavbar();

// Add a small delay to ensure dataFile is set by navbar loading
setTimeout(loadChart, 100);

// Create custom legend
function createCustomLegend() {
  customLegend.innerHTML = '';
  
  filteredDatasets.forEach((dataset, index) => {
    const legendItem = document.createElement('div');
    legendItem.className = 'legend-item';
    legendItem.setAttribute('data-index', dataset.originalIndex);
    
    if (dataset.hidden) {
      legendItem.classList.add('hidden');
    }
    
    legendItem.innerHTML = `
      <div class="legend-color" style="background-color: ${dataset.borderColor}"></div>
      <span>${dataset.label}</span>
    `;
    
    legendItem.addEventListener('click', () => {
      toggleDataset(dataset.originalIndex);
    });
    
    customLegend.appendChild(legendItem);
  });
  
  updateVisibleCount();
}

// Toggle dataset visibility
function toggleDataset(originalIndex) {
  if (chart) {
    const meta = chart.getDatasetMeta(originalIndex);
    meta.hidden = meta.hidden === null ? !chart.data.datasets[originalIndex].hidden : null;
    
    // Update dataset hidden state
    allDatasets[originalIndex].hidden = meta.hidden;
    
    chart.update();
    createCustomLegend();
  }
}

// Toggle all datasets (filtered list only)
function toggleAllDatasets(show) {
  if (chart) {
    filteredDatasets.forEach((dataset) => {
      const meta = chart.getDatasetMeta(dataset.originalIndex);
      meta.hidden = show ? null : true;
      dataset.hidden = !show;
      // Also update in allDatasets array
      allDatasets[dataset.originalIndex].hidden = !show;
    });
    
    chart.update();
    createCustomLegend();
  }
}

// Combined filtering functionality
function applyFilters() {
  filteredDatasets = allDatasets.filter(dataset => {
    // Search filter
    const matchesSearch = dataset.label.toLowerCase().includes(currentSearchTerm.toLowerCase());
    
    // Distance filter - use meta.distance in km
    const distance = dataset.meta ? (dataset.meta.distance / 1000) : 0;
    const matchesDistance = distance >= currentMinDistance && distance <= currentMaxDistance;
    
    return matchesSearch && matchesDistance;
  });
  createCustomLegend();
}

// Update distance labels and range track
function updateDistanceLabels() {
  minDistanceLabel.textContent = `${currentMinDistance} km`;
  maxDistanceLabel.textContent = `${currentMaxDistance} km`;
  updateRangeTrack();
}

// Update the visual range track
function updateRangeTrack() {
  const rangeTrack = document.getElementById('rangeTrack');
  const min = parseFloat(minDistanceSlider.min);
  const max = parseFloat(minDistanceSlider.max);
  const minVal = currentMinDistance;
  const maxVal = currentMaxDistance;
  
  const minPercent = ((minVal - min) / (max - min)) * 100;
  const maxPercent = ((maxVal - min) / (max - min)) * 100;
  
  rangeTrack.style.left = minPercent + '%';
  rangeTrack.style.width = (maxPercent - minPercent) + '%';
}

// Auto-detect distance range from data
function autoDetectDistanceRange() {
  if (allDatasets.length === 0) return;
  
  // Extract distances from meta.distance in km
  const distances = allDatasets
    .filter(d => d.meta && d.meta.distance > 0)
    .map(d => d.meta.distance / 1000);
   console.log(distances);
  if (distances.length === 0) return;
  
  const minDist = Math.floor(Math.min(...distances));
  const maxDist = Math.ceil(Math.max(...distances));
  
  // Update slider ranges
  minDistanceSlider.min = minDist;
  minDistanceSlider.max = maxDist;
  minDistanceSlider.value = minDist;
  
  maxDistanceSlider.min = minDist;
  maxDistanceSlider.max = maxDist;
  maxDistanceSlider.value = maxDist;
  
  currentMinDistance = minDist;
  currentMaxDistance = maxDist;

  updateDistanceLabels();
  updateRangeTrack();
}

// Update visible count and button text
function updateVisibleCount() {
  const visible = allDatasets.filter(dataset => !dataset.hidden).length;
  visibleCount.textContent = `${visible}/${allDatasets.length} visible`;
  
  // Update button text with filtered dataset count
  const filteredCount = filteredDatasets.length;
  showAllBtn.textContent = `Show ${filteredCount}`;
  hideAllBtn.textContent = `Hide ${filteredCount}`;
}

// Event handlers
searchInput.addEventListener('input', (e) => {
  currentSearchTerm = e.target.value;
  applyFilters();
});

minDistanceSlider.addEventListener('input', (e) => {
  currentMinDistance = parseFloat(e.target.value);
  // Ensure min doesn't exceed max
  if (currentMinDistance > currentMaxDistance) {
    currentMaxDistance = currentMinDistance;
    maxDistanceSlider.value = currentMinDistance;
  }
  updateDistanceLabels();
  applyFilters();
});

maxDistanceSlider.addEventListener('input', (e) => {
  currentMaxDistance = parseFloat(e.target.value);
  // Ensure max doesn't go below min
  if (currentMaxDistance < currentMinDistance) {
    currentMinDistance = currentMaxDistance;
    minDistanceSlider.value = currentMaxDistance;
  }
  updateDistanceLabels();
  applyFilters();
});

// Helper function to format seconds as mm:ss
function formatSecondsAsTime(seconds) {
  const minutes = Math.floor(seconds / 60);
  const remainingSeconds = Math.floor(seconds % 60);
  return `${minutes}:${remainingSeconds.toString().padStart(2, '0')}`;
}

// Load and setup chart
function loadChart() {
  const mainContent = document.querySelector('.main-content');
  
  if (!dataFile) {
    statusDiv.innerHTML = 'No chart data available. Generate some charts first using the processor.';
    statusDiv.style.color = '#666';
    
    // Add loading state class and hide controls/chart
    mainContent.classList.add('loading-state');
    const controlsPanel = document.querySelector('.controls-panel');
    const chartContainer = document.querySelector('.chart-container');
    if (controlsPanel) controlsPanel.style.display = 'none';
    if (chartContainer) chartContainer.style.display = 'none';
    
    return;
  }
  
  // Initially add loading state
  mainContent.classList.add('loading-state');

  fetch(dataFile)
  .then(response => {
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    return response.json();
  })
  .then(config => {
    statusDiv.style.display = 'none';
    
    // Remove loading state and show controls/chart
    const mainContent = document.querySelector('.main-content');
    mainContent.classList.remove('loading-state');
    const controlsPanel = document.querySelector('.controls-panel');
    const chartContainer = document.querySelector('.chart-container');
    if (controlsPanel) controlsPanel.style.display = 'block';
    if (chartContainer) chartContainer.style.display = 'block';
    
    // Disable default legend
    config.options.plugins.legend.display = false;
    
    // Update Y-axis to show time format
    if (config.options.scales && config.options.scales.y) {
      config.options.scales.y.ticks = {
        callback: function(value) {
          return formatSecondsAsTime(value);
        }
      };
      
      // Update Y-axis title
      config.options.scales.y.title.text = 'Lap Time (mm:ss)';
    }
    
    // Add tooltip formatting for time
    if (!config.options.plugins.tooltip) {
      config.options.plugins.tooltip = {};
    }
    config.options.plugins.tooltip.callbacks = {
      label: function(context) {
        const time = formatSecondsAsTime(context.parsed.y);
        return `${context.dataset.label}: ${time}`;
      }
    };
    
    // Store datasets with original indices
    allDatasets = config.data.datasets.map((dataset, index) => ({
      ...dataset,
      originalIndex: index,
      hidden: false
    }));
    
    // Auto-detect distance range and setup sliders
    autoDetectDistanceRange();
    
    filteredDatasets = [...allDatasets];
    
    // Create chart
    chart = new Chart(ctx, config);
    
    // Create custom legend
    createCustomLegend();
  })
  .catch(error => {
    console.error('Error loading chart data:', error);
    statusDiv.innerHTML = `Error loading chart data from "${dataFile}": ${error.message}`;
    statusDiv.style.color = 'red';
  });
}

// Reset all filters to default state
function resetFilters() {
  // Clear search term
  currentSearchTerm = '';
  searchInput.value = '';
  
  // Reset distance sliders to their full range
  autoDetectDistanceRange();
  
  // Show all datasets
  allDatasets.forEach((dataset) => {
    const meta = chart.getDatasetMeta(dataset.originalIndex);
    meta.hidden = null;
    dataset.hidden = false;
  });
  
  // Update chart and legend
  chart.update();
  applyFilters();
}

// Make functions global for button onclick
window.toggleAllDatasets = toggleAllDatasets;
window.resetFilters = resetFilters;
