// Static, font-independent SVG based on the approved Kiedy Siatka? design.
// No canvas, animation, fallback wordmark or hidden legacy logo.
export default function BrandSignature() {
  return <div className="vh-brand-signature">
    <img
      src={import.meta.env.BASE_URL + 'kiedy-siatka-logo.svg'}
      alt="Kiedy Siatka?"
      width="340"
      height="184"
      decoding="async"
      draggable={false}
    />
  </div>;
}
