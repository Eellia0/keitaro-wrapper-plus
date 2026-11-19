import OfferPicker from './OfferPicker';
import React, { useEffect, useState } from 'react';
import CampaignSearch from './CampaignSearch';
import PublicationPreview from './PublicationPreview';

async function request(path, body) {
  const response = await fetch(`/api/editor/${path}`, body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : undefined);
  const data = await response.json();
  if (!response.ok) { const error = new Error(typeof data.detail === 'string' ? data.detail : 'Проверьте введённые данные'); error.status = response.status; throw error; }
  return data;
}

function readRecent() {
  try {
    const items = JSON.parse(localStorage.getItem('keitaro-plus-recent') || '[]');
    return Array.isArray(items) ? items.filter(item => Number.isInteger(item.id) && typeof item.name === 'string').slice(0, 8) : [];
  } catch { return []; }
}

export default function Editor({offers, initialCampaign}) {
  const [recent, setRecent] = useState(readRecent);
  const [previewId, setPreviewId] = useState(null);
  const [campaignId, setCampaignId] = useState('');
  const [campaign, setCampaign] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [choices, setChoices] = useState({});
  const [weights, setWeights] = useState({});
  async function execute(callback) {
    setBusy(true);
    setError('');
    try { setCampaign(await callback()); setPreviewId(null); setWeights({}); setChoices({}); }
    catch (error) { setError(error.message); }
    finally { setBusy(false); }
  }
  function openCampaign(id) {
    setCampaignId(String(id));
    execute(async () => {
      try { return await request(`${id}`); }
      catch (error) {
        if (error.status !== 404) throw error;
        return request(`${id}/fetch`, {});
      }
    });
  }
  useEffect(() => {
    if (initialCampaign) openCampaign(initialCampaign.id);
  }, [initialCampaign]);
  useEffect(() => {
    if (!campaign) return;
    const items = [{id: campaign.id, name: campaign.name}, ...readRecent().filter(item => item.id !== campaign.id)].slice(0, 8);
    setRecent(items);
    try { localStorage.setItem('keitaro-plus-recent', JSON.stringify(items)); } catch { /* History is optional when storage is unavailable. */ }
  }, [campaign?.id]);
  function act(stream, operation, offer_id = 0, share = 0) {
    execute(() => request(`${campaign.id}/streams/${stream.id}`, {revision: campaign.revision, operation, offer_id, share: Number(share)}));
  }
  return <section className="editor">
    <h1>Редактор кампании</h1><CampaignSearch disabled={busy} onSelect={openCampaign} />
    {recent.length > 0 && <div className="recent-campaigns"><h3>Последние кампании</h3>{recent.map(item => <button className="secondary" disabled={busy} key={item.id} onClick={() => openCampaign(item.id)}>{item.name} · #{item.id}</button>)}</div>}
    <form onSubmit={event => {event.preventDefault(); execute(() => request(`${campaignId}/fetch`, {}));}}>
      <label>ID кампании<input type="number" min="1" required value={campaignId} onChange={event => setCampaignId(event.target.value)} /></label>
      <button disabled={busy}>Загрузить из Keitaro</button>
      {campaignId && <button className="secondary" type="button" disabled={busy} onClick={() => execute(() => request(`${campaignId}`))}>Открыть локальный черновик</button>}
    </form>
    {error && <p className="error" role="alert">{error}</p>}
    {busy && <p role="status">Выполняем запрос…</p>}
    {campaign && <>
      <h2>{campaign.name} · #{campaign.id}</h2>
      {campaign.streams.map(stream => <article key={stream.id} className={`stream ${stream.dirty ? 'dirty' : ''}`}>
        <h3>{stream.name} <small>#{stream.id} · {stream.dirty ? 'Есть неопубликованные изменения' : 'Сохранено'}</small></h3>
        {stream.offers.length === 0 ? <p>В потоке нет офферов.</p> : <div className="table-wrap"><table><thead><tr><th>Оффер</th><th>Доля</th><th>Действия</th></tr></thead><tbody>
          {stream.offers.map(offer => <tr className={offer.removed ? 'removed' : ''} key={offer.id}>
            <td>#{offer.id} {offer.name}{offer.removed && <small>Удалён из потока</small>}</td>
            <td>{offer.share}% {offer.pinned && '· закреплена'}</td>
            <td>{offer.removed ? <button disabled={busy} onClick={() => act(stream, 'add', offer.id)}>Вернуть</button> : <>
              <button className="secondary" disabled={busy} onClick={() => act(stream, 'remove', offer.id)}>Удалить</button>
              <div className="weight-control"><input aria-label={`Доля оффера ${offer.id}`} type="number" min="0" max="100" value={weights[`${stream.id}-${offer.id}`] ?? offer.share} onChange={event => setWeights({...weights, [`${stream.id}-${offer.id}`]: event.target.value})} />
              <button className="secondary" disabled={busy} onClick={() => act(stream, offer.pinned ? 'unpin' : 'pin', offer.id, weights[`${stream.id}-${offer.id}`] ?? offer.share)}>{offer.pinned ? 'Открепить' : 'Закрепить'}</button></div>
            </>}</td>
          </tr>)}
        </tbody></table></div>}
        <p>Сумма активных долей — {stream.offers.filter(offer => !offer.removed).reduce((sum, offer) => sum + offer.share, 0)}%</p>
        {stream.editable && <div className="add-offer"><OfferPicker offers={offers.filter(offer => !stream.offers.some(item => item.id === offer.id && !item.removed))} value={choices[stream.id] || ''} disabled={busy} onChange={id => setChoices(current => ({...current, [stream.id]: id}))} /><button disabled={busy || !choices[stream.id]} onClick={() => act(stream, 'add', Number(choices[stream.id]))}>Добавить</button></div>}
        {stream.editable && !offers.some(offer => !stream.offers.some(item => item.id === offer.id && !item.removed)) && <p role="status">Все доступные офферы уже в потоке. Keitaro вернул активных офферов: {offers.length}.</p>}
        {stream.editable && <button className="secondary" disabled={busy || !stream.offers.some(offer => !offer.removed)} onClick={() => act(stream, 'equalize')}>Распределить поровну</button>}
        {stream.dirty && <div className="stream-actions"><button disabled={busy} onClick={() => setPreviewId(stream.id)}>Просмотреть изменения</button><button className="secondary" disabled={busy} onClick={() => act(stream, 'cancel')}>Отменить изменения</button></div>}
        {previewId === stream.id && <PublicationPreview stream={stream} busy={busy} onCancel={() => setPreviewId(null)} onPublish={() => act(stream, 'push')} />}
      </article>)}
    </>}
  </section>;
}


