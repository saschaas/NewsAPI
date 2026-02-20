"""
Stealth JavaScript payloads to mask browser automation fingerprints.

These scripts are injected via context.add_init_script() before any page
scripts run, making the headless browser harder to detect.
"""


# Remove navigator.webdriver flag - the primary bot detection signal
HIDE_WEBDRIVER = """
Object.defineProperty(navigator, 'webdriver', {
    get: () => undefined,
});
"""

# Mock navigator.plugins - headless Chrome has 0 plugins, real Chrome has ~5
MOCK_PLUGINS = """
Object.defineProperty(navigator, 'plugins', {
    get: () => {
        const plugins = [
            { name: 'Chrome PDF Plugin', filename: 'internal-pdf-viewer', description: 'Portable Document Format' },
            { name: 'Chrome PDF Viewer', filename: 'mhjfbmdgcfjbbpaeojofohoefgiehjai', description: '' },
            { name: 'Native Client', filename: 'internal-nacl-plugin', description: '' },
        ];
        plugins.length = 3;
        return plugins;
    },
});
"""

# Mock navigator.languages to match Accept-Language headers
MOCK_LANGUAGES = """
Object.defineProperty(navigator, 'languages', {
    get: () => ['en-US', 'en'],
});
"""

# Mock chrome.runtime - exists in real Chrome but not in headless/automated
MOCK_CHROME_RUNTIME = """
if (!window.chrome) {
    window.chrome = {};
}
if (!window.chrome.runtime) {
    window.chrome.runtime = {
        connect: function() {},
        sendMessage: function() {},
    };
}
"""

# Override Permissions.query for notification permission fingerprint
MOCK_PERMISSIONS = """
const originalQuery = window.navigator.permissions.query;
window.navigator.permissions.query = (parameters) => (
    parameters.name === 'notifications' ?
        Promise.resolve({ state: Notification.permission }) :
        originalQuery(parameters)
);
"""

# Delete Playwright-specific globals
DELETE_PLAYWRIGHT_GLOBALS = """
delete window.__playwright;
delete window.__pw_manual;
"""


def get_combined_stealth_script() -> str:
    """
    Returns a single combined JavaScript string with all stealth payloads.

    Inject this via context.add_init_script() before navigating to any page.
    """
    return "\n".join([
        HIDE_WEBDRIVER,
        MOCK_PLUGINS,
        MOCK_LANGUAGES,
        MOCK_CHROME_RUNTIME,
        MOCK_PERMISSIONS,
        DELETE_PLAYWRIGHT_GLOBALS,
    ])
