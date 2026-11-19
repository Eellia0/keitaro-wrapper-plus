import React, {useEffect, useRef, useState} from 'react';

export default function CampaignSearch({onSelect, disabled}) {
  const [query, setQuery] = useState('');
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(false);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(-1);
  const [error, setError] = useState('');
  const container = useRef(null);
  const requestVersion = useRef(0);

  useEffect(() => {
    const version = ++requestVersion.current;
    const controller = new AbortController();
    setItems([]);
    setActive(-1);
    setError('');
    if (!query.trim() || disabled) {
      setLoading(false);
      return () => controller.abort();
    }
    setLoading(true);
    const timer = setTimeout(async () => {
      try {
        const response = await fetch(`/api/campaign-search?q=${encodeURIComponent(query.trim())}`, {signal: controller.signal});
        const data = await response.json();
        if (!response.ok) throw new Error(data.detail || 'Не удалось найти кампании');
        if (version === requestVersion.current) setItems(data);
      } catch (error) {
        if (error.name !== 'AbortError' && version === requestVersion.current) setError(error.message);
      } finally {
        if (version === requestVersion.current) setLoading(false);
      }
    }, 350);
    return () => {clearTimeout(timer); controller.abort();};
  }, [query, disabled]);

  useEffect(() => {
    function closeOutside(event) {
      if (!container.current?.contains(event.target)) setOpen(false);
    }
    document.addEventListener('pointerdown', closeOutside);
    return () => document.removeEventListener('pointerdown', closeOutside);
  }, []);

  function select(item) {
    setOpen(false);
    setActive(-1);
    onSelect(item.id);
  }
  function keyDown(event) {
    if (event.key === 'Escape') {setOpen(false); setActive(-1);}
    if (event.key === 'ArrowDown') {
      event.preventDefault();
      setOpen(true);
      setActive(index => Math.min(index + 1, items.length - 1));
    }
    if (event.key === 'ArrowUp') {
      event.preventDefault();
      setActive(index => Math.max(index - 1, 0));
    }
    if (event.key === 'Enter' && open) {
      event.preventDefault();
      if (active >= 0 && items[active]) select(items[active]);
    }
  }
  const show = open && Boolean(query.trim()) && !disabled;
  return <div className="campaign-search" ref={container} onBlur={event => {if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);}}>
    <label htmlFor="campaign-query">Найти кампанию</label>
    <div className="autocomplete">
      <input id="campaign-query" role="combobox" aria-autocomplete="list" aria-expanded={show} aria-controls="campaign-options" aria-activedescendant={show && active >= 0 ? `campaign-option-${active}` : undefined} disabled={disabled} value={query} maxLength={150} onFocus={() => setOpen(true)} onKeyDown={keyDown} onChange={event => {setQuery(event.target.value); setOpen(true);}} placeholder="Начните вводить название или ID" />
      {show && <div className="suggestion-panel">
        {loading && <p role="status">Ищем кампании…</p>}
        {error && <p className="error" role="alert">{error}</p>}
        {!loading && !error && items.length === 0 && <p role="status">Кампании не найдены.</p>}
        <ul id="campaign-options" role="listbox" aria-label="Найденные кампании">{items.map((item,index) => <li id={`campaign-option-${index}`} key={item.id} role="option" aria-selected={active === index} className={active === index ? 'active' : ''} onPointerDown={event => event.preventDefault()} onMouseEnter={() => setActive(index)} onClick={() => select(item)}>{item.name}<small>#{item.id}</small></li>)}</ul>
      </div>}
    </div>
    <small>Выберите кампанию из подсказок. Стрелки и Enter также работают.</small>
  </div>;
}
