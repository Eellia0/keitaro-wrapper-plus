import React, { useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import './styles.css';
import Editor from './Editor';

async function api(path, options) {
  const response = await fetch(`/api/${path}`, options);
  const data = await response.json();
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : 'Проверьте заполненные поля');
  return data;
}

function App() {
  const [tab, setTab] = useState('create');
  const [editorCampaign, setEditorCampaign] = useState(null);
  const [lists, setLists] = useState(null);
  const [error, setError] = useState('');
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);
  const [requestId, setRequestId] = useState(() => crypto.randomUUID());
  const [query, setQuery] = useState('');
  const [form, setForm] = useState({name: '', country: '', offer_id: '', domain_id: '', group_id: '', traffic_source_id: ''});

  async function load() {
    setError('');
    try {
      const [domains, groups, sources, offers, settings] = await Promise.all(
        ['domains', 'groups', 'traffic-sources', 'offers', 'settings'].map(path => api(path))
      );
      setLists({domains, groups, sources, offers, settings});
      setForm(current => ({...current,
        domain_id: domains[0]?.id || '',
        group_id: (groups.find(item => item.name === 'FORTESTS') || groups[0])?.id || '',
        traffic_source_id: (sources.find(item => item.name === 'FORTESTS') || sources[0])?.id || '',
      }));
    } catch (error) { setError(error.message); }
  }
  useEffect(() => { load(); }, []);

  function update(event) {
    setForm({...form, [event.target.name]: event.target.value});
    setResult(null);
    setRequestId(crypto.randomUUID());
  }
  async function submit(event) {
    event.preventDefault();
    setBusy(true);
    setError('');
    setResult(null);
    try {
      const payload = {...form, request_id: requestId};
      for (const key of ['offer_id', 'domain_id', 'group_id', 'traffic_source_id']) payload[key] = Number(payload[key]);
      setResult(await api('campaigns', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(payload)}));
    } catch (error) { setError(error.message); }
    finally { setBusy(false); }
  }
  const search = query.trim().toLowerCase();
  const matches = lists?.offers.filter(item => `${item.id} ${item.name}`.toLowerCase().includes(search)) || [];
  const selectedOffer = lists?.offers.find(item => String(item.id) === String(form.offer_id));
  const visibleOffers = selectedOffer && !matches.some(item => item.id === selectedOffer.id)
    ? [selectedOffer, ...matches] : matches;
  return <main>
    <header><span>Keitaro<span className="brand-accent"> / </span>Wrapper</span><span>Создание кампании</span></header>
    <nav className="workspace-tabs" aria-label="Разделы приложения"><button className={tab === 'create' ? 'selected' : 'secondary'} aria-pressed={tab === 'create'} onClick={() => setTab('create')}>Создать</button><button className={tab === 'edit' ? 'selected' : 'secondary'} aria-pressed={tab === 'edit'} onClick={() => setTab('edit')}>Редактировать</button></nav>
    <div hidden={tab !== 'create'}><section>
      <h1>Новая кампания</h1>
      <p>Задайте гео и оффер. Приложение настроит два потока и ссылку кампании.</p>
      {error && <div className="error" role="alert"><p>{error}</p>{!lists && <button onClick={load}>Повторить загрузку</button>}</div>}
      {!lists && !error && <p role="status">Загружаем справочники Keitaro…</p>}
      {lists && <form onSubmit={submit}>
        <fieldset disabled={busy || Boolean(result)}>
          <label>Название кампании<input name="name" value={form.name} onChange={update} required maxLength={120} placeholder="campaign1" /><small>Префикс {lists.settings.campaign_prefix} добавляется автоматически.</small></label>
          <label>Код страны<input name="country" value={form.country} onChange={event => {setForm({...form, country: event.target.value.toUpperCase()}); setResult(null); setRequestId(crypto.randomUUID());}} required pattern="[A-Z]{2}" maxLength={2} placeholder="AU" /></label>
          <label>Поиск оффера<input value={query} onChange={event => setQuery(event.target.value)} placeholder="Название или ID" /><small>Доступно офферов: {lists.offers.length}. Найдено: {matches.length}.</small></label>
          {matches.length === 0 && <div role="status" className="offer-empty"><p>{lists.offers.length ? 'По этому запросу офферы не найдены.' : 'Keitaro вернул пустой список активных офферов.'}</p>{query && <button type="button" onClick={() => setQuery('')}>Показать все офферы</button>}</div>}
          <label>Оффер<select name="offer_id" value={form.offer_id} onChange={update} required><option value="">Выберите оффер</option>{visibleOffers.map(item => <option key={item.id} value={item.id}>#{item.id} · {item.name}</option>)}</select></label>
          <div className="form-grid">{[['domain_id', 'Домен', lists.domains], ['group_id', 'Группа', lists.groups], ['traffic_source_id', 'Источник', lists.sources]].map(([key, label, items]) => <label key={key}>{label}<select name={key} value={form[key]} onChange={update} required><option value="">Выберите</option>{items.map(item => <option key={item.id} value={item.id}>{item.name}</option>)}</select></label>)}</div>
          <div className="flow-preview"><strong>Маршрут перехода</strong><p>{form.country || 'Выбранная страна'} → Google</p><p>Остальные посетители → выбранный оффер</p></div>
          <button type="submit">{busy ? 'Создаём кампанию…' : 'Создать в Keitaro'}</button>
        </fieldset>
      </form>}
      {result && <div className="success" role="status"><h2>Кампания создана</h2><p>{result.name} · #{result.id}</p><p><a href={result.url} target="_blank" rel="noreferrer">Ссылка кампании</a> · <a href={result.admin_url} target="_blank" rel="noreferrer">Открыть в Keitaro</a></p><button onClick={() => {setEditorCampaign({id: result.id}); setTab('edit');}}>Редактировать кампанию</button> <button onClick={() => {setResult(null); setForm({...form, name: ''}); setRequestId(crypto.randomUUID());}}>Создать ещё одну</button></div>}
    </section></div>
    <div hidden={tab !== 'edit'}>{lists && <Editor offers={lists.offers} initialCampaign={editorCampaign} />}</div>
  </main>;
}
createRoot(document.getElementById('root')).render(<App />);
