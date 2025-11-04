// Configuration for proposal storage
export const storageConfig = {
  // Lambda function configuration for DynamoDB backend
  lambda: {
    functionName: 'proposal-service',
    region: 'us-east-1',
    // For now, we'll use direct Lambda invocation
    // Later we can switch to API Gateway endpoints
    useDirectInvocation: true,
    apiGatewayUrl: null // Will be set when API Gateway is configured
  },
  
  // Storage preferences
  preferences: {
    enableCloudStorage: true,
    fallbackToLocalStorage: true,
    syncOnLoad: true
  }
}