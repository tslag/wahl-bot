import React from 'react';
import DOMPurify from 'dompurify';

import '../css/Message.css';

function parseTable(html) {
  const doc = new DOMParser().parseFromString(html, 'text/html');
  const table = doc.querySelector('table');
  if (!table) return null;

  // headers
  const firstRow = table.querySelector('tr');
  const headers = firstRow ? Array.from(firstRow.querySelectorAll('th,td')).map(n => n.textContent.trim()) : [];

  // rows
  const rows = Array.from(table.querySelectorAll('tr')).slice(headers.length ? 1 : 0)
    .map(tr => Array.from(tr.querySelectorAll('td')).map(td => ({ html: td.innerHTML })));

  return { headers, rows };
}

function Message({ message }) {
  const content = message.content ?? '';

  // plain-text fast path
  const looksLikeHtml = /<[^>]+>/i.test(content);
  if (!looksLikeHtml) return <div className="chat-message-content">{content}</div>;

  // sanitize (allow links; DOMPurify will strip scripts etc.)
  const safe = DOMPurify.sanitize(content, { ADD_ATTR: ['target'] });

  // if there's a table, parse and render as React table for control
  if (/<table/i.test(safe)) {
    const parsed = parseTable(safe);
    if (parsed) {
      return (
        <div className="table-wrap">
          <table className="styled-table" role="table">
            <thead>
              <tr>{parsed.headers.map((h,i)=>(<th key={i} scope="col">{h}</th>))}</tr>
            </thead>
            <tbody>
              {parsed.rows.map((r,ri)=>(
                <tr key={ri}>{r.map((c,ci)=>(<td key={ci} dangerouslySetInnerHTML={{__html: c.html}} />))}</tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }
  }

  // fallback: safe HTML rendering (e.g. paragraphs, links)
  return <div className="chat-message-content" dangerouslySetInnerHTML={{ __html: safe }} />;
}

export default Message;