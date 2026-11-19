import React, {useEffect, useId, useRef, useState} from 'react';

export default function OfferPicker({offers, value, onChange, disabled = false, required = false}) {
  const selected = offers.find(offer => String(offer.id) === String(value));
  const label = offer => `#${offer.id} · ${offer.name.startsWith(`${offer.id} `) ? offer.name.slice(String(offer.id).length + 1) : offer.name}`;
  const [query, setQuery] = useState(selected ? label(selected) : '');
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const input = useRef(null);
  const editing = useRef(false);
  const id = useId();
  const matches = offers.filter(offer => `${offer.id} ${offer.name}`.toLowerCase().includes(query.trim().toLowerCase()));
  const options = selected && query === label(selected) ? offers : matches;
  useEffect(() => {if (editing.current) {editing.current = false; return;} setQuery(selected ? label(selected) : '');}, [value]);
  useEffect(() => {input.current?.setCustomValidity(required && !selected ? 'Выберите оффер из подсказок' : '');}, [required, selected]);
  function choose(offer) {onChange(offer.id); setQuery(label(offer)); setOpen(false); setActive(0);}
  const shown = open && !disabled;
  return <div className="offer-picker" onBlur={event => {if (!event.currentTarget.contains(event.relatedTarget)) setOpen(false);}}>
    <label htmlFor={id}>Оффер</label>
    <div className="autocomplete">
      <input id={id} ref={input} role="combobox" aria-autocomplete="list" aria-expanded={shown} aria-controls={`${id}-options`} aria-activedescendant={shown && options[active] ? `${id}-option-${active}` : undefined} autoComplete="off" disabled={disabled} required={required} value={query} placeholder="Название или ID оффера" onFocus={() => setOpen(true)} onChange={event => {setQuery(event.target.value); if (value) {editing.current = true; onChange('');} setOpen(true); setActive(0);}} onKeyDown={event => {
        if (event.key === 'Enter') {event.preventDefault(); if (shown && options[active]) choose(options[active]);}
        if (event.key === 'Escape') setOpen(false);
        if (event.key === 'ArrowDown') {event.preventDefault(); setOpen(true); setActive(index => Math.min(index + 1, Math.max(options.length - 1, 0)));}
        if (event.key === 'ArrowUp') {event.preventDefault(); setActive(index => Math.max(index - 1, 0));}
      }} />
      {shown && <div className="suggestion-panel"><ul id={`${id}-options`} role="listbox" aria-label="Офферы">{options.map((offer,index) => <li id={`${id}-option-${index}`} role="option" aria-selected={index === active} className={index === active ? 'active' : ''} key={offer.id} onMouseEnter={() => setActive(index)} onPointerDown={event => event.preventDefault()} onClick={() => choose(offer)}>{label(offer)}</li>)}</ul>{options.length === 0 && <p role="status">{offers.length ? 'Совпадений нет' : 'Нет офферов для добавления'}</p>}</div>}
    </div>
  </div>;
}
