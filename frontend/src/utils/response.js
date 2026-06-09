export function unwrapApiResponse(response, fallbackMessage = '请求失败') {
  if (response?.code !== undefined && ![0, 200, 201].includes(Number(response.code))) {
    throw new Error(response.message || fallbackMessage)
  }

  return response?.data ?? response
}
