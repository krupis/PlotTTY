const repository = "krupis/QT_PlotTTY";
const releasesUrl = `https://github.com/${repository}/releases/latest`;

function preferredAsset() {
  const platform = navigator.userAgentData?.platform || navigator.platform || "";
  if (/Win/i.test(platform)) return "windows-x64.zip";
  if (/Mac/i.test(platform)) return "macos";
  if (/Linux/i.test(platform)) return "linux-x64.tar.gz";
  return null;
}

function matchesAsset(assetName, suffix) {
  return assetName.toLowerCase().endsWith(suffix.toLowerCase());
}

async function loadLatestRelease() {
  try {
    const response = await fetch(`https://api.github.com/repos/${repository}/releases/latest`, {
      headers: { Accept: "application/vnd.github+json" }
    });
    if (!response.ok) throw new Error(`GitHub returned ${response.status}`);

    const release = await response.json();
    const links = document.querySelectorAll("[data-asset]");
    links.forEach((link) => {
      const asset = release.assets.find((item) => matchesAsset(item.name, link.dataset.asset));
      if (asset) link.href = asset.browser_download_url;
    });

    const releaseLabel = document.querySelector("#release-label");
    releaseLabel.textContent = `Version ${release.tag_name}`;

    const preferred = preferredAsset();
    const primary = document.querySelector("#primary-download");
    if (preferred === "macos") {
      primary.href = "#downloads";
      primary.querySelector("span").textContent = "Choose macOS download";
      return;
    }
    const preferredLink = preferred && document.querySelector(`[data-asset="${preferred}"]`);
    if (preferredLink?.href && preferredLink.href !== releasesUrl) {
      primary.href = preferredLink.href;
      primary.querySelector("span").textContent = preferred.startsWith("windows")
        ? "Download for Windows"
        : preferred.startsWith("macos")
          ? "Download for macOS"
          : "Download for Linux";
    }
  } catch (error) {
    console.info("Using the GitHub releases page as the download fallback.", error);
  }
}

loadLatestRelease();
