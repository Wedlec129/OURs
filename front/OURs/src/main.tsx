import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'

import {Button} from "antd";

createRoot(document.getElementById('root')!).render(
  <StrictMode>
      <Button>Default Button</Button>
  </StrictMode>,
)
