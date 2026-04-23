const state = {
  manifest: null,
  folders: [],
  selectedFolder: null,
  filterText: "",
  visibleImages: [],
  lightboxIndex: -1,
};

const folderAliases = {
  sfh: "spot_forest_hard",
  sibl: "spot_indoor_building_loop",
  sodpsl: "spot_outdoor_day_penno_short_loop",
  sods: "spot_outdoor_day_skatepark_1",
};

const elements = {
  folderList: document.getElementById("folderList"),
  folderCaption: document.getElementById("folderCaption"),
  folderTitle: document.getElementById("folderTitle"),
  visibleCount: document.getElementById("visibleCount"),
  folderCount: document.getElementById("folderCount"),
  totalCount: document.getElementById("totalCount"),
  statusMessage: document.getElementById("statusMessage"),
  galleryGrid: document.getElementById("galleryGrid"),
  searchInput: document.getElementById("searchInput"),
  lightbox: document.getElementById("lightbox"),
  lightboxImage: document.getElementById("lightboxImage"),
  lightboxFolder: document.getElementById("lightboxFolder"),
  lightboxTitle: document.getElementById("lightboxTitle"),
  openOriginal: document.getElementById("openOriginal"),
  lightboxIndex: document.getElementById("lightboxIndex"),
  closeLightbox: document.getElementById("closeLightbox"),
  prevImage: document.getElementById("prevImage"),
  nextImage: document.getElementById("nextImage"),
};

function getFolderParts(folderName) {
  return folderName.split("/").filter(Boolean);
}

function prettifySegment(segment) {
  return segment
    .replace(/^covariance_metrics_/, "")
    .replace(/_/g, " ");
}

function isSequenceOverlayRawFolder(parts) {
  return (
    parts[0] === "rpe_analysis_individual" &&
    parts[parts.length - 1] === "overlay_raw" &&
    parts[parts.length - 2] === "rpe_translation_m" &&
    parts.length >= 5
  );
}

function getSequenceOverlayRawLabel(folderName) {
  const parts = getFolderParts(folderName);
  if (!isSequenceOverlayRawFolder(parts)) {
    return null;
  }

  return folderAliases[parts[1]] || parts[1];
}

function getFolderLabel(folderName) {
  const sequenceOverlayRawLabel = getSequenceOverlayRawLabel(folderName);
  if (sequenceOverlayRawLabel) {
    return sequenceOverlayRawLabel;
  }

  return getFolderParts(folderName)
    .map((segment) => folderAliases[segment] || segment)
    .join(" / ");
}

function getFolderContext(folderName) {
  const parts = getFolderParts(folderName);
  if (isSequenceOverlayRawFolder(parts)) {
    return `${prettifySegment(parts[2])} / ${prettifySegment(parts[3])} / raw overlays`;
  }

  return parts
    .map((segment) => folderAliases[segment] || segment)
    .join(" / ");
}

function formatTitle(fileName) {
  const baseName = fileName.replace(/\.[^.]+$/, "");
  const cleaned = baseName.replace(/^\d+[_-]?/, "").replace(/[_-]+/g, " ").trim();
  if (!cleaned) {
    return fileName;
  }

  return cleaned.replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function folderDescription(folder) {
  if (!folder.images.length) {
    return "No images";
  }

  const firstImage = formatTitle(folder.images[0].file);
  return `${folder.images.length} plots from ${getFolderContext(folder.name)}, starting with ${firstImage}`;
}

function parseHash() {
  const rawHash = window.location.hash.startsWith("#") ? window.location.hash.slice(1) : "";
  const params = new URLSearchParams(rawHash);

  return {
    folder: params.get("folder"),
    image: params.get("image"),
  };
}

function setHash(folderName, imageFile, replace = false) {
  const params = new URLSearchParams();
  if (folderName) {
    params.set("folder", folderName);
  }
  if (imageFile) {
    params.set("image", imageFile);
  }

  const nextHash = params.toString();
  const nextUrl = `${window.location.pathname}${window.location.search}${nextHash ? `#${nextHash}` : ""}`;

  if (replace) {
    history.replaceState(null, "", nextUrl);
  } else if (window.location.hash !== (nextHash ? `#${nextHash}` : "")) {
    history.pushState(null, "", nextUrl);
  }
}

function setStatus(message, isError = false) {
  elements.statusMessage.textContent = message;
  elements.statusMessage.classList.toggle("error", isError);
}

function renderFolders() {
  elements.folderList.innerHTML = "";

  state.folders.forEach((folder) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "folder-button";
    button.dataset.folder = folder.name;
    button.classList.toggle("active", folder.name === state.selectedFolder?.name);

    const title = document.createElement("div");
    title.className = "folder-button-title";
    title.innerHTML = `<code>${getFolderLabel(folder.name)}</code><span class="folder-count">${folder.images.length}</span>`;

    const description = document.createElement("small");
    description.textContent = folderDescription(folder);

    button.append(title, description);
    button.addEventListener("click", () => {
      selectFolder(folder.name);
      closeLightbox(true);
      setHash(folder.name, null);
    });

    elements.folderList.appendChild(button);
  });
}

function renderGallery() {
  const selectedFolder = state.selectedFolder;
  if (!selectedFolder) {
    setStatus("No image folders were found in manifest.json.", true);
    elements.galleryGrid.innerHTML = "";
    elements.visibleCount.textContent = "0";
    return;
  }

  const query = state.filterText.trim().toLowerCase();
  const visibleImages = selectedFolder.images.filter((image) => {
    if (!query) {
      return true;
    }

    const haystack = `${image.file} ${formatTitle(image.file)}`.toLowerCase();
    return haystack.includes(query);
  });

  state.visibleImages = visibleImages;
  elements.visibleCount.textContent = String(visibleImages.length);
  const folderLabel = getFolderLabel(selectedFolder.name);
  elements.folderCaption.textContent = `${selectedFolder.images.length} plots from ${getFolderContext(selectedFolder.name)}`;
  elements.folderTitle.textContent = `${folderLabel} gallery`;

  if (!visibleImages.length) {
    elements.galleryGrid.innerHTML = "";
    setStatus("No plots match the current filter.");
    return;
  }

  setStatus(`Showing ${visibleImages.length} image${visibleImages.length === 1 ? "" : "s"} from ${folderLabel}.`);
  elements.galleryGrid.innerHTML = "";

  visibleImages.forEach((image, index) => {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "thumb-card";
    button.innerHTML = `
      <div class="thumb-art">
        <img src="${image.path}" alt="${formatTitle(image.file)}" loading="lazy">
      </div>
      <div class="thumb-meta">
        <h3>${formatTitle(image.file)}</h3>
        <p>${image.file}</p>
      </div>
    `;

    button.addEventListener("click", () => {
      openLightbox(index);
      setHash(selectedFolder.name, image.file);
    });

    elements.galleryGrid.appendChild(button);
  });
}

function selectFolder(folderName) {
  const nextFolder = state.folders.find((folder) => folder.name === folderName) || state.folders[0] || null;
  state.selectedFolder = nextFolder;
  renderFolders();
  renderGallery();
}

function openLightbox(index) {
  const image = state.visibleImages[index];
  if (!image || !state.selectedFolder) {
    return;
  }

  state.lightboxIndex = index;
  elements.lightboxImage.src = image.path;
  elements.lightboxImage.alt = formatTitle(image.file);
  elements.lightboxFolder.textContent = getFolderLabel(state.selectedFolder.name);
  elements.lightboxTitle.textContent = formatTitle(image.file);
  elements.openOriginal.href = image.path;
  elements.lightboxIndex.textContent = `${index + 1} / ${state.visibleImages.length}`;
  elements.lightbox.classList.remove("hidden");
  elements.lightbox.setAttribute("aria-hidden", "false");
  document.body.style.overflow = "hidden";
}

function closeLightbox(skipHashUpdate = false) {
  state.lightboxIndex = -1;
  elements.lightbox.classList.add("hidden");
  elements.lightbox.setAttribute("aria-hidden", "true");
  document.body.style.overflow = "";

  if (!skipHashUpdate) {
    setHash(state.selectedFolder?.name, null, true);
  }
}

function moveLightbox(direction) {
  if (state.lightboxIndex < 0 || !state.visibleImages.length || !state.selectedFolder) {
    return;
  }

  const nextIndex = (state.lightboxIndex + direction + state.visibleImages.length) % state.visibleImages.length;
  openLightbox(nextIndex);
  setHash(state.selectedFolder.name, state.visibleImages[nextIndex].file, true);
}

function applyHashState() {
  if (!state.folders.length) {
    return;
  }

  const { folder, image } = parseHash();
  const folderExists = state.folders.some((entry) => entry.name === folder);
  const targetFolder = folderExists ? folder : state.folders[0].name;

  if (!state.selectedFolder || state.selectedFolder.name !== targetFolder) {
    selectFolder(targetFolder);
  }

  if (!image) {
    closeLightbox(true);
    return;
  }

  const imageIndex = state.visibleImages.findIndex((entry) => entry.file === image);
  if (imageIndex >= 0) {
    openLightbox(imageIndex);
  }
}

async function loadManifest() {
  if (window.location.protocol === "file:") {
    throw new Error("Open this project through GitHub Pages or a local static server so the manifest can be loaded.");
  }

  const response = await fetch("./manifest.json", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Could not load manifest.json (${response.status}).`);
  }

  return response.json();
}

function normalizeManifest(manifest) {
  const folders = Array.isArray(manifest.folders) ? manifest.folders : [];
  return folders
    .map((folder) => ({
      name: folder.name,
      images: Array.isArray(folder.images) ? folder.images : [],
    }))
    .filter((folder) => folder.name && folder.images.length)
    .sort((left, right) => left.name.localeCompare(right.name));
}

function bindEvents() {
  elements.searchInput.addEventListener("input", (event) => {
    state.filterText = event.target.value;
    closeLightbox(true);
    renderGallery();
  });

  elements.closeLightbox.addEventListener("click", () => closeLightbox());
  elements.prevImage.addEventListener("click", () => moveLightbox(-1));
  elements.nextImage.addEventListener("click", () => moveLightbox(1));

  elements.lightbox.addEventListener("click", (event) => {
    if (event.target instanceof HTMLElement && event.target.dataset.closeLightbox === "true") {
      closeLightbox();
    }
  });

  window.addEventListener("keydown", (event) => {
    if (elements.lightbox.classList.contains("hidden")) {
      return;
    }

    if (event.key === "Escape") {
      closeLightbox();
    }

    if (event.key === "ArrowLeft") {
      moveLightbox(-1);
    }

    if (event.key === "ArrowRight") {
      moveLightbox(1);
    }
  });

  window.addEventListener("hashchange", applyHashState);
}

async function initialize() {
  bindEvents();

  try {
    state.manifest = await loadManifest();
    state.folders = normalizeManifest(state.manifest);

    elements.folderCount.textContent = String(state.folders.length);
    const totalImages = state.folders.reduce((sum, folder) => sum + folder.images.length, 0);
    elements.totalCount.textContent = String(totalImages);

    if (!state.folders.length) {
      throw new Error("manifest.json loaded, but no image folders were found.");
    }

    renderFolders();
    applyHashState();

    if (!window.location.hash) {
      setHash(state.selectedFolder?.name, null, true);
    }
  } catch (error) {
    console.error(error);
    setStatus(error.message, true);
    elements.folderCaption.textContent = "Manifest unavailable";
    elements.folderTitle.textContent = "Viewer setup still needed";
    elements.galleryGrid.innerHTML = "";
  }
}

initialize();
