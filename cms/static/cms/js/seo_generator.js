document.addEventListener('DOMContentLoaded', function () {
    const btn = document.getElementById('generate-seo-btn');
    if (!btn) return;

    btn.addEventListener('click', function () {
        // Determine type and fields
        const type = btn.dataset.type;
        let data = { type: type };

        // Map fields based on type
        if (type === 'startup') {
            const name = document.getElementById('id_name');
            const desc = document.getElementById('id_description');
            if (name) data.title = name.value;
            if (desc) data.description = desc.value;
        } else if (type === 'story') {
            const title = document.getElementById('id_title');
            const content = document.getElementById('id_content');
            if (title) data.title = title.value;
            if (content) data.content = content.value;
            // Also description from content if possible
            data.description = "Story content analysis";
        }

        if (!data.title) {
            alert('Please fill in the Name/Title first.');
            return;
        }

        btn.innerText = 'Generating...';
        btn.disabled = true;

        fetch('/api/cms/generate-seo/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                // Add CSRF token if needed, usually available in cookie or input
            },
            body: JSON.stringify(data)
        })
            .then(response => response.json())
            .then(result => {
                btn.innerText = 'Generate SEO with AI';
                btn.disabled = false;

                if (result.error) {
                    alert('Error: ' + result.error);
                    return;
                }

                // Populate fields
                const metaTitle = document.getElementById('id_meta_title');
                const metaDesc = document.getElementById('id_meta_description');

                if (metaTitle && result.meta_title) metaTitle.value = result.meta_title;
                if (metaDesc && result.meta_description) metaDesc.value = result.meta_description;

                // You can map more fields here
                console.log("SEO Generated", result);
            })
            .catch(err => {
                console.error(err);
                btn.innerText = 'Generate SEO with AI';
                btn.disabled = false;
                alert('Network error');
            });
    });
});
