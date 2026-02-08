class KeePassXCOTPCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: 'open' });
    this._entities = [];
    this._updating = false;
  }

  setConfig(config) {
    if (!config) {
      throw new Error('Invalid configuration');
    }
    this._config = {
      title: config.title || '🔐 KeePassXC OTP',
      show_gauge: config.show_gauge !== false,
      show_copy_button: config.show_copy_button !== false,
      layout: config.layout || 'auto',
      ...config
    };
  }

  set hass(hass) {
    this._hass = hass;
    
    // Auto-discover all keepassxc_otp entities
    if (!this._updating) {
      this._updateEntities();
    }
    
    this._render();
  }

  _updateEntities() {
    if (!this._hass) return;
    
    const entities = [];
    const currentUserId = this._hass.user?.id;
    const isAdmin = this._hass.user?.is_admin || false;
    const showAllUsers = this._config.show_all_users || false;
    
    Object.keys(this._hass.states).forEach(entity_id => {
      if (entity_id.startsWith('sensor.keepassxc_otp_')) {
        const state = this._hass.states[entity_id];
        const entityUserId = state.attributes?.user_id;
        
        // Filter by current user unless admin view with show_all_users enabled
        if (showAllUsers && isAdmin) {
          // Admin can see all entities when show_all_users is true
          entities.push(entity_id);
        } else if (!entityUserId) {
          // Legacy entities without user_id (shared mode)
          entities.push(entity_id);
        } else if (entityUserId === currentUserId) {
          // User's own entities
          entities.push(entity_id);
        }
        // Otherwise, skip entity (belongs to another user)
      }
    });
    
    this._entities = entities.sort();
  }

  _render() {
    if (!this._hass || !this._entities) return;

    const styles = `
      <style>
        :host {
          display: block;
        }
        .card {
          padding: 16px;
          background: var(--ha-card-background, var(--card-background-color, white));
          border-radius: var(--ha-card-border-radius, 12px);
          box-shadow: var(--ha-card-box-shadow, 0 2px 8px rgba(0,0,0,0.1));
        }
        .header {
          font-size: 24px;
          font-weight: 500;
          margin-bottom: 16px;
          color: var(--primary-text-color);
        }
        .otp-item {
          display: flex;
          align-items: center;
          padding: 12px;
          margin-bottom: 12px;
          background: var(--secondary-background-color);
          border-radius: 8px;
          gap: 16px;
        }
        .otp-gauge {
          flex-shrink: 0;
          width: 80px;
          height: 80px;
          position: relative;
        }
        .gauge-svg {
          transform: rotate(-90deg);
        }
        .gauge-bg {
          fill: none;
          stroke: var(--disabled-text-color);
          stroke-width: 8;
          opacity: 0.2;
        }
        .gauge-progress {
          fill: none;
          stroke-width: 8;
          stroke-linecap: round;
          transition: stroke-dashoffset 0.3s ease, stroke 0.3s ease;
        }
        .gauge-text {
          position: absolute;
          top: 50%;
          left: 50%;
          transform: translate(-50%, -50%);
          font-size: 18px;
          font-weight: bold;
        }
        .otp-info {
          flex-grow: 1;
        }
        .otp-name {
          font-size: 18px;
          font-weight: 600;
          color: var(--primary-text-color);
          margin-bottom: 4px;
        }
        .otp-details {
          font-size: 12px;
          color: var(--secondary-text-color);
          margin-bottom: 8px;
        }
        .otp-code {
          font-size: 28px;
          font-family: 'Courier New', monospace;
          letter-spacing: 4px;
          color: var(--primary-color);
          font-weight: bold;
          user-select: all;
        }
        .otp-actions {
          display: flex;
          gap: 8px;
        }
        .copy-button {
          padding: 8px 16px;
          background: var(--primary-color);
          color: white;
          border: none;
          border-radius: 6px;
          cursor: pointer;
          font-size: 14px;
          transition: opacity 0.2s;
        }
        .copy-button:hover {
          opacity: 0.8;
        }
        .copy-button:active {
          opacity: 0.6;
        }
        .copied {
          background: var(--success-color, green) !important;
        }
        .color-green { stroke: var(--success-color, #4caf50); }
        .color-yellow { stroke: var(--warning-color, #ff9800); }
        .color-red { stroke: var(--error-color, #f44336); }
      </style>
    `;

    const content = this._entities.map(entity_id => {
      const state = this._hass.states[entity_id];
      if (!state) return '';

      const code = state.state;
      const formattedCode = code.substring(0, 3) + ' ' + code.substring(3);
      const remaining = state.attributes.time_remaining || 0;
      const period = state.attributes.period || 30;
      const name = state.attributes.friendly_name || entity_id;
      const issuer = state.attributes.issuer || '';
      const account = state.attributes.account || '';
      
      // Calculate gauge
      const percentage = (remaining / period) * 100;
      const circumference = 2 * Math.PI * 32; // radius = 32
      const offset = circumference - (percentage / 100) * circumference;
      
      // Determine color
      let colorClass = 'color-green';
      if (percentage < 33) colorClass = 'color-red';
      else if (percentage < 66) colorClass = 'color-yellow';

      return `
        <div class="otp-item">
          ${this._config.show_gauge ? `
            <div class="otp-gauge">
              <svg class="gauge-svg" width="80" height="80" viewBox="0 0 80 80">
                <circle class="gauge-bg" cx="40" cy="40" r="32"></circle>
                <circle 
                  class="gauge-progress ${colorClass}" 
                  cx="40" cy="40" r="32"
                  stroke-dasharray="${circumference}"
                  stroke-dashoffset="${offset}"
                ></circle>
              </svg>
              <div class="gauge-text">${remaining}s</div>
            </div>
          ` : ''}
          
          <div class="otp-info">
            <div class="otp-name">${name}</div>
            <div class="otp-details">
              ${issuer ? `${issuer} • ` : ''}${account || ''}
            </div>
            <div class="otp-code">${formattedCode}</div>
          </div>
          
          ${this._config.show_copy_button ? `
            <div class="otp-actions">
              <button 
                class="copy-button" 
                data-entity="${entity_id}"
                data-token="${code}"
              >
                📋 Copy
              </button>
            </div>
          ` : ''}
        </div>
      `;
    }).join('');

    this.shadowRoot.innerHTML = `
      ${styles}
      <div class="card">
        <div class="header">${this._config.title}</div>
        ${content || '<div>No OTP entities found</div>'}
      </div>
    `;

    // Add event listeners for copy buttons
    this.shadowRoot.querySelectorAll('.copy-button').forEach(button => {
      button.addEventListener('click', (e) => this._handleCopy(e));
    });
  }

  async _handleCopy(event) {
    const button = event.target;
    const entityId = button.dataset.entity;
    const token = button.dataset.token;
    
    try {
      // Try modern clipboard API
      if (navigator.clipboard && navigator.clipboard.writeText) {
        await navigator.clipboard.writeText(token);
        this._showCopySuccess(button);
      } else {
        // Fallback: call service
        await this._hass.callService('keepassxc_otp', 'copy_token', {
          entity_id: entityId
        });
        this._showCopySuccess(button);
      }
    } catch (err) {
      console.error('Failed to copy:', err);
      // Fallback to service call
      await this._hass.callService('keepassxc_otp', 'copy_token', {
        entity_id: entityId
      });
    }
  }

  _showCopySuccess(button) {
    const originalText = button.textContent;
    button.textContent = '✅ Copied!';
    button.classList.add('copied');
    
    setTimeout(() => {
      button.textContent = originalText;
      button.classList.remove('copied');
    }, 2000);
  }

  getCardSize() {
    return this._entities.length * 2 + 1;
  }
}

customElements.define('keepassxc-otp-card', KeePassXCOTPCard);

window.customCards = window.customCards || [];
window.customCards.push({
  type: 'keepassxc-otp-card',
  name: 'KeePassXC OTP Card',
  description: 'Display and copy KeePassXC OTP tokens with auto-discovery',
  preview: true,
  documentationURL: 'https://github.com/XtraLarge/keepassxc_otp',
});

console.info(
  '%c KEEPASSXC-OTP-CARD %c Version 1.0.0 ',
  'color: white; background: #0066cc; font-weight: 700;',
  'color: #0066cc; background: white; font-weight: 700;'
);
