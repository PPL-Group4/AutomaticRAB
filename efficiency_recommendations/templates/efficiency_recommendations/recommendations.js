/**
 * Efficiency Recommendations & Notifications Integration
 * This script fetches and displays efficiency recommendations and price deviation warnings
 */

(function() {
  'use strict';

  // Configuration
  const NOTIFICATION_ENDPOINT = '/efficiency_recommendations/jobs/{job_id}/notifications/';
  const PRICE_DEVIATION_ENDPOINT = '/efficiency_recommendations/jobs/{job_id}/price-deviations/';
  
  let currentJobId = null;
  let notificationCheckInterval = null;

  /**
   * Initialize the efficiency recommendations panel
   */
  function initEfficiencyRecommendations(jobId) {
    if (!jobId) {
      console.warn('No job ID provided for efficiency recommendations');
      return;
    }

    currentJobId = jobId;
    
    // Show the panel
    const panel = document.getElementById('efficiencyRecommendationsPanel');
    if (panel) {
      panel.style.display = 'block';
    }

    // Fetch recommendations immediately
    fetchAndDisplayRecommendations();

    // Set up periodic checks for price changes (every 5 seconds)
    if (notificationCheckInterval) {
      clearInterval(notificationCheckInterval);
    }
    notificationCheckInterval = setInterval(fetchAndDisplayRecommendations, 5000);
  }

  /**
   * Fetch and display all recommendations
   */
  async function fetchAndDisplayRecommendations() {
    if (!currentJobId) return;

    try {
      // Fetch both notifications and price deviations in parallel
      const [notificationsData, deviationsData] = await Promise.all([
        fetchNotifications(currentJobId),
        fetchPriceDeviations(currentJobId)
      ]);

      // Display results
      displayNotifications(notificationsData);
      displayPriceDeviations(deviationsData);
      updateCostWeightRecommendation();

      // Show "no warnings" if everything is clear
      const hasWarnings = 
        (notificationsData && notificationsData.items_not_in_ahsp > 0) ||
        (deviationsData && deviationsData.deviations_found > 0);
      
      document.getElementById('noWarningsSection').style.display = hasWarnings ? 'none' : 'block';

    } catch (error) {
      console.error('Error fetching recommendations:', error);
    }
  }

  /**
   * Fetch notifications for items not in AHSP
   */
  async function fetchNotifications(jobId) {
    const url = NOTIFICATION_ENDPOINT.replace('{job_id}', jobId);
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch notifications: ${response.status}`);
    }
    
    return await response.json();
  }

  /**
   * Fetch price deviation warnings
   */
  async function fetchPriceDeviations(jobId) {
    const url = PRICE_DEVIATION_ENDPOINT.replace('{job_id}', jobId);
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error(`Failed to fetch price deviations: ${response.status}`);
    }
    
    return await response.json();
  }

  /**
   * Display notifications for items not in database
   */
  function displayNotifications(data) {
    const section = document.getElementById('notInDatabaseSection');
    const countBadge = document.getElementById('notInDatabaseCount');
    const list = document.getElementById('notInDatabaseList');

    if (!data || !data.notifications || data.notifications.length === 0) {
      section.style.display = 'none';
      return;
    }

    // Update count
    countBadge.textContent = data.items_not_in_ahsp || 0;

    // Clear and populate list
    list.innerHTML = '';
    data.notifications.forEach(notification => {
      const li = document.createElement('li');
      li.className = 'mb-1';
      li.innerHTML = `
        <strong>${escapeHtml(notification.item_name)}</strong>
        <span class="text-muted">— ${escapeHtml(notification.message)}</span>
      `;
      list.appendChild(li);
    });

    section.style.display = 'block';
    
    // Add inline warnings to table rows
    addInlineNotificationWarnings(data.notifications);
  }

  /**
   * Display price deviation warnings
   */
  function displayPriceDeviations(data) {
    const section = document.getElementById('priceDeviationSection');
    const countBadge = document.getElementById('priceDeviationCount');
    const tbody = document.getElementById('priceDeviationTableBody');

    if (!data || !data.deviations || data.deviations.length === 0) {
      section.style.display = 'none';
      return;
    }

    // Update count
    countBadge.textContent = data.deviations_found || 0;

    // Clear and populate table
    tbody.innerHTML = '';
    data.deviations.forEach(deviation => {
      const tr = document.createElement('tr');
      
      const severityClass = getSeverityClass(deviation.deviation_level);
      const deviationSign = deviation.deviation_percentage > 0 ? '+' : '';
      
      tr.innerHTML = `
        <td><strong>${escapeHtml(deviation.item_name)}</strong></td>
        <td>
          <span class="deviation-badge ${severityClass}">
            ${escapeHtml(deviation.deviation_level)}
          </span>
        </td>
        <td class="text-end">Rp ${formatNumber(deviation.actual_price)}</td>
        <td class="text-end">Rp ${formatNumber(deviation.reference_price)}</td>
        <td class="text-end">
          <span class="${deviation.deviation_percentage > 0 ? 'text-danger' : 'text-success'} fw-bold">
            ${deviationSign}${deviation.deviation_percentage.toFixed(1)}%
          </span>
        </td>
        <td class="small">${escapeHtml(deviation.message)}</td>
      `;
      
      tbody.appendChild(tr);
    });

    section.style.display = 'block';
    
    // Add inline warnings to table rows
    addInlinePriceWarnings(data.deviations);
  }

  /**
   * Update cost weight recommendation based on chart data
   */
  function updateCostWeightRecommendation() {
    const section = document.getElementById('costWeightRecommendation');
    const textElement = document.getElementById('costWeightRecommendationText');
    
    // Get data from cost weight chart if available
    const chartBox = document.getElementById('costWeightChartBox');
    if (!chartBox || chartBox.style.display === 'none') {
      section.style.display = 'none';
      return;
    }

    // Get the highest cost item from the chart
    const legendContainer = document.getElementById('costWeightLegend');
    if (legendContainer && legendContainer.children.length > 1) {
      const firstItem = legendContainer.children[1]; // Skip the h6 header
      if (firstItem) {
        const itemName = firstItem.querySelector('div[style*="font-weight: 600"]');
        const itemInfo = firstItem.querySelector('div[style*="font-size: 0.75rem"]');
        
        if (itemName && itemInfo) {
          const name = itemName.textContent;
          const infoText = itemInfo.textContent;
          const percentMatch = infoText.match(/\(([\d.]+)%\)/);
          
          if (percentMatch) {
            const percentage = percentMatch[1];
            textElement.innerHTML = `
              <strong>${escapeHtml(name)}</strong> accounts for <strong>${percentage}%</strong> of the total cost. 
              Consider evaluating material prices for this job to ensure cost efficiency.
            `;
            section.style.display = 'block';
            return;
          }
        }
      }
    }

    section.style.display = 'none';
  }

  /**
   * Add inline warning indicators to table rows for items not in database
   */
  function addInlineNotificationWarnings(notifications) {
    notifications.forEach(notification => {
      const itemName = notification.item_name;
      
      // Find the row with this item
      const rows = document.querySelectorAll('#rabTables tbody tr');
      rows.forEach(row => {
        const descCell = row.querySelector('td:nth-child(2)');
        if (descCell && descCell.textContent.trim() === itemName) {
          const warnHost = descCell.querySelector('.price-warning-host');
          if (warnHost) {
            // Check if warning already exists
            if (!warnHost.querySelector('.warning-chip-not-in-db')) {
              const chip = document.createElement('div');
              chip.className = 'warning-chip warning-chip-not-in-db mt-1';
              chip.innerHTML = `
                <span class="dot"></span>
                <span>Not in database - manual price required</span>
              `;
              warnHost.appendChild(chip);
            }
          }
        }
      });
    });
  }

  /**
   * Add inline warning indicators to table rows for price deviations
   */
  function addInlinePriceWarnings(deviations) {
    deviations.forEach(deviation => {
      const itemName = deviation.item_name;
      
      // Find the row with this item
      const rows = document.querySelectorAll('#rabTables tbody tr');
      rows.forEach(row => {
        const descCell = row.querySelector('td:nth-child(2)');
        if (descCell && descCell.textContent.includes(itemName)) {
          const warnHost = descCell.querySelector('.price-warning-host');
          if (warnHost) {
            // Remove existing price warning if any
            const existing = warnHost.querySelector('.warning-chip-price-deviation');
            if (existing) {
              existing.remove();
            }
            
            const isCritical = deviation.deviation_level === 'CRITICAL';
            const chip = document.createElement('div');
            chip.className = `warning-chip ${isCritical ? 'critical' : ''} warning-chip-price-deviation mt-1`;
            chip.innerHTML = `
              <span class="dot"></span>
              <span>Price ${deviation.deviation_percentage > 0 ? 'higher' : 'lower'} than reference (${deviation.deviation_percentage > 0 ? '+' : ''}${deviation.deviation_percentage.toFixed(1)}%)</span>
            `;
            warnHost.appendChild(chip);
          }
        }
      });
    });
  }

  /**
   * Get CSS class for severity level
   */
  function getSeverityClass(level) {
    const levelMap = {
      'MODERATE': 'deviation-moderate',
      'HIGH': 'deviation-high',
      'CRITICAL': 'deviation-critical'
    };
    return levelMap[level] || 'deviation-moderate';
  }

  /**
   * Format number with thousand separators
   */
  function formatNumber(number) {
    return parseFloat(number).toLocaleString('id-ID', {
      minimumFractionDigits: 0,
      maximumFractionDigits: 2
    });
  }

  /**
   * Escape HTML to prevent XSS
   */
  function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
  }

  /**
   * Clean up when leaving the page
   */
  function cleanup() {
    if (notificationCheckInterval) {
      clearInterval(notificationCheckInterval);
      notificationCheckInterval = null;
    }
  }

  // Expose functions globally
  window.EfficiencyRecommendations = {
    init: initEfficiencyRecommendations,
    refresh: fetchAndDisplayRecommendations,
    cleanup: cleanup
  };

  // Clean up on page unload
  window.addEventListener('beforeunload', cleanup);

})();
