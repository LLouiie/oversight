import Document, { Head, Html, Main, NextScript } from "next/document";

export default class MyDocument extends Document {
  render() {
    return (
      <Html lang="en" data-theme="dark">
        <Head />
        <body>
          <script
            dangerouslySetInnerHTML={{
              __html:
                '(function(){try{var t=localStorage.getItem("oversight_theme");if(t==="light"||t==="dark"){document.documentElement.setAttribute("data-theme",t);}}catch(e){}})();',
            }}
          />
          <Main />
          <NextScript />
        </body>
      </Html>
    );
  }
}

