export function changesFor(stream) {
  const saved = new Map(stream.saved.map(offer => [offer.id, offer]));
  return stream.offers.flatMap(offer => {
    const before = saved.get(offer.id);
    const changes = [];
    if ((!before || before.removed) && !offer.removed) changes.push('Добавлен в поток');
    if (before && !before.removed && offer.removed) changes.push('Удалён из потока');
    if (before && before.share !== offer.share) changes.push(`Доля ${before.share}% → ${offer.share}%`);
    if (Boolean(before?.pinned) !== offer.pinned) changes.push(offer.pinned ? 'Доля закреплена локально' : 'Доля откреплена локально');
    return changes.length ? [{id: offer.id, name: offer.name, text: changes.join('. ')}] : [];
  });
}


