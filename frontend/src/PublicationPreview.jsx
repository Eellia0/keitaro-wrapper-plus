import React from 'react';

import { changesFor } from './changes';

export default function PublicationPreview({stream, busy, onCancel, onPublish}) {
  const active = stream.offers.filter(offer => !offer.removed);
  const total = active.reduce((sum, offer) => sum + offer.share, 0);
  const valid = active.length > 0 && total === 100;
  return <aside className="publication-preview" aria-labelledby="publication-title">
    <h2 id="publication-title">Публикация потока «{stream.name}»</h2>
    <p>Эти изменения будут применены в Keitaro.</p>
    <ul>{changesFor(stream).map(item => <li key={item.id}><strong>#{item.id} {item.name}</strong><p>{item.text}</p></li>)}</ul>
    <p>Активных офферов: {active.length}. Сумма долей: {total}%.</p>
    {!valid && <p role="alert" className="error">Нужен хотя бы один активный оффер и сумма долей 100%.</p>}
    <div className="stream-actions"><button disabled={busy || !valid} onClick={onPublish}>Подтвердить публикацию</button><button className="secondary" disabled={busy} onClick={onCancel}>Вернуться к редактированию</button></div>
  </aside>;
}

