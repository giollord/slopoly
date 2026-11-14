// <model-viewer> helpers called from Blazor: swap the palette (base colour) texture without reloading the model.
window.slopolyViewer = {
    scrollToEnd(element) { if (element) element.scrollTop = element.scrollHeight; },
    async setPalette(viewer, url) {
        await customElements.whenDefined("model-viewer");
        if (!viewer.loaded) await new Promise(resolve => viewer.addEventListener("load", resolve, { once: true }));
        const texture = await viewer.createTexture(url);
        for (const material of viewer.model.materials) {
            const slot = material.pbrMetallicRoughness.baseColorTexture;
            slot.setTexture(texture);
            const sampler = slot.texture?.sampler;
            if (sampler) { sampler.setMagFilter(9728); sampler.setMinFilter(9728); } // nearest: keep palette cells crisp
        }
    }
};
