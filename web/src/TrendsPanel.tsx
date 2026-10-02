/** Extension point for resource trends (#9). */
export function TrendsPanel() {
  return (
    <section className="panel" id="trends">
      <h2>Trends</h2>
      <p className="muted">
        Historical resource charts will land here (issue #9). Status above uses{" "}
        <code>/api/status</code>.
      </p>
    </section>
  );
}
