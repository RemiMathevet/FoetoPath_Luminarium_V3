// ponytail: shared helpers for slide cards (admin fœtus + admin placenta)

function slideStatusDot(status) {
    const colors = { labeled_normal: '#27ae60', labeled_patho: '#e67e22' };
    const labels = { labeled_normal: 'Normal', labeled_patho: 'Patho', unlabeled: 'Non examiné' };
    const c = colors[status] || '#888';
    const l = labels[status] || 'Non examiné';
    return `<span style="display:inline-flex;align-items:center;gap:3px;font-size:10px;color:${c}" title="${l}"><span style="display:inline-block;width:8px;height:8px;border-radius:50%;background:${c}"></span>${l}</span>`;
}

function slideLabelsInline(sl) {
    const diags = sl.diagnoses_resolved || [];
    if (!diags.length && !sl.slide_note) return '';
    let html = '<table style="width:100%;border-collapse:collapse;font-size:10px;margin-top:6px;border-top:1px solid var(--border)">';
    for (const d of diags) {
        html += `<tr><td style="padding:2px 0;color:var(--text3,var(--muted));font-family:monospace;white-space:nowrap;vertical-align:top;width:1%">${escHtml(d.id)}</td><td style="padding:2px 4px;color:var(--text2)">${escHtml(d.label_fr)}</td></tr>`;
    }
    if (sl.slide_note) {
        html += `<tr><td colspan="2" style="padding:2px 0;color:var(--text2);font-style:italic">${escHtml(sl.slide_note)}</td></tr>`;
    }
    html += '</table>';
    return html;
}

function slideSummaryTable(slides) {
    const labeled = slides.filter(sl => sl.diagnoses_resolved?.length || sl.slide_note || sl.organ_statuses?.length);
    if (!labeled.length) return '';
    let html = `<div style="margin-top:16px;border:1px solid var(--border);border-radius:6px;overflow:hidden">
        <div style="padding:6px 10px;background:var(--surface2);font-size:12px;font-weight:600;color:var(--accent)">Labels &amp; annotations par lame</div>
        <table style="width:100%;border-collapse:collapse;font-size:11px">
        <tr style="background:var(--surface2)">
            <th style="text-align:left;padding:4px 8px;font-weight:600">Lame</th>
            <th style="text-align:left;padding:4px 8px;font-weight:600">Organe(s)</th>
            <th style="text-align:left;padding:4px 8px;font-weight:600">Code FOETO</th>
            <th style="text-align:left;padding:4px 8px;font-weight:600">Description</th>
            <th style="text-align:left;padding:4px 8px;font-weight:600">Note</th>
        </tr>`;
    for (const sl of labeled) {
        const diags = sl.diagnoses_resolved || [];
        const organs = (sl.organ_statuses || []).map(o => {
            const color = o.status === 'normal' ? '#27ae60' : '#e67e22';
            return `<span style="color:${color}">${escHtml(o.organ)}</span>`;
        }).join(', ');
        const rows = Math.max(diags.length, 1);
        for (let i = 0; i < rows; i++) {
            const d = diags[i];
            html += '<tr style="border-bottom:1px solid var(--border)">';
            if (i === 0) {
                html += `<td style="padding:3px 8px;font-weight:600;vertical-align:top;white-space:nowrap" rowspan="${rows}">${escHtml(sl.nom_lame)}</td>`;
                html += `<td style="padding:3px 8px;vertical-align:top" rowspan="${rows}">${organs || ''}</td>`;
            }
            html += `<td style="padding:3px 8px;font-family:monospace;font-size:10px;color:var(--text3,var(--muted));vertical-align:top">${d ? escHtml(d.id) : ''}</td>`;
            html += `<td style="padding:3px 8px">${d ? escHtml(d.label_fr) : ''}</td>`;
            if (i === 0) html += `<td style="padding:3px 8px;font-style:italic;color:var(--text3,var(--muted));vertical-align:top" rowspan="${rows}">${sl.slide_note ? escHtml(sl.slide_note) : ''}</td>`;
            html += '</tr>';
        }
    }
    html += '</table></div>';
    return html;
}
