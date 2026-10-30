export function Pagination({
  page,
  pageSize,
  total,
  onChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onChange: (page: number) => void;
}) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (total === 0) return null;

  return (
    <div className="hd-pager">
      <span className="hd-pager__info">
        共 {total} 条 · 第 {page}/{pages} 页
      </span>
      <div className="hd-pager__btns">
        <button className="hd-btn hd-btn--sm" disabled={page <= 1} onClick={() => onChange(page - 1)}>
          上一页
        </button>
        <button
          className="hd-btn hd-btn--sm"
          disabled={page >= pages}
          onClick={() => onChange(page + 1)}
        >
          下一页
        </button>
      </div>
    </div>
  );
}
