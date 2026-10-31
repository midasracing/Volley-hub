// Static, font-independent SVG based on the approved Kiedy Siatka? design.
// No canvas, animation, fallback wordmark or hidden legacy logo.
export default function BrandSignature() {
  return <div className="vh-brand-signature">
    <img
      src={import.meta.env.BASE_URL + 'kiedy-siatka-logo.svg?v=2'}
      alt="Kiedy Siatka?"
      width="1180"
      height="655"
      decoding="async"
      draggable={false}
    />
  </div>;
}
