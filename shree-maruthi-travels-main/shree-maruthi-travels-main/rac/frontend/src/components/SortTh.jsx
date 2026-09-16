const SortTh = ({ field, label, sortBy, sortOrder, onSort }) => {
  const active = sortBy === field
  return (
    <th>
      <button type="button" className={`sort-th${active ? ' is-active' : ''}`} onClick={() => onSort(field)}>
        <span>{label}</span>
        <span className="sort-arrow" aria-hidden="true">
          {active ? (sortOrder === 'ASC' ? '↑' : '↓') : '↕'}
        </span>
      </button>
    </th>
  )
}

export default SortTh
